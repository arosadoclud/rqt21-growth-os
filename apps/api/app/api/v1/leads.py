from __future__ import annotations

import csv
import io
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app import audit
from app.deps import (
    OrgContext,
    current_org,
    current_user,
    get_session,
    require_lead_export,
    require_lead_write,
)
from app.models.brand import Brand
from app.models.campaign import Campaign
from app.models.content import ContentItem
from app.models.enums import LeadActivityType, LeadSource, LeadStatus
from app.models.lead import Lead, LeadActivity
from app.models.product import Product
from app.models.tracking import TrackingLink
from app.models.user import User
from app.schemas.leads import (
    LeadActivityCreate,
    LeadActivityRead,
    LeadCreate,
    LeadImport,
    LeadRead,
    LeadStatusChangeRequest,
    LeadUpdate,
    sanitize_lead_activity,
    serialize_lead_for_role,
)
from app.utils.phone import InvalidPhoneNumber, normalize_phone, org_default_country
from app.utils.public_id import make as make_public_id

router = APIRouter(prefix="/leads", tags=["leads"])


def _normalize_contact_fields(
    db: Session, org_id: uuid.UUID, phone: str | None, whatsapp: str | None
) -> tuple[str | None, str | None]:
    """Normalize phone/whatsapp to E.164 using the organization's default
    country. Raises 422 on a non-empty value that can't be parsed."""
    default_country = org_default_country(db, org_id)
    try:
        return (
            normalize_phone(phone, default_country),
            normalize_phone(whatsapp, default_country),
        )
    except InvalidPhoneNumber as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _get_or_404(db: Session, org_id: uuid.UUID, lead_id: uuid.UUID) -> Lead:
    row = db.execute(
        select(Lead).where(Lead.id == lead_id, Lead.organization_id == org_id)
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="lead not found")
    return row


def _validate_relations(
    db: Session,
    org_id: uuid.UUID,
    *,
    brand_id: uuid.UUID | None,
    product_id: uuid.UUID | None,
    campaign_id: uuid.UUID | None,
    content_item_id: uuid.UUID | None,
    tracking_link_id: uuid.UUID | None,
) -> None:
    checks: list[tuple[type, uuid.UUID | None, str]] = [
        (Brand, brand_id, "brand"),
        (Product, product_id, "product"),
        (Campaign, campaign_id, "campaign"),
        (ContentItem, content_item_id, "content_item"),
        (TrackingLink, tracking_link_id, "tracking_link"),
    ]
    for model, val, label in checks:
        if val is None:
            continue
        ok = db.execute(
            select(model.id).where(model.id == val, model.organization_id == org_id)
        ).scalar_one_or_none()
        if ok is None:
            raise HTTPException(
                status_code=400, detail=f"{label} not found in organization"
            )


def _log_activity(
    db: Session,
    *,
    org_id: uuid.UUID,
    lead_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
    activity_type: LeadActivityType,
    description: str,
    metadata: dict | None = None,
) -> LeadActivity:
    row = LeadActivity(
        public_id=make_public_id("la"),
        organization_id=org_id,
        lead_id=lead_id,
        actor_user_id=actor_user_id,
        activity_type=activity_type,
        description=description,
        activity_metadata=metadata or {},
    )
    db.add(row)
    db.flush()
    return row


@router.get("", response_model=list[LeadRead])
def list_leads(
    q: str | None = Query(default=None),
    status_filter: LeadStatus | None = Query(default=None, alias="status"),
    source: LeadSource | None = None,
    campaign_id: uuid.UUID | None = None,
    product_id: uuid.UUID | None = None,
    brand_id: uuid.UUID | None = None,
    content_item_id: uuid.UUID | None = None,
    tracking_link_id: uuid.UUID | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    org: OrgContext = Depends(current_org),
    db: Session = Depends(get_session),
) -> list[LeadRead]:
    stmt = (
        select(Lead)
        .where(Lead.organization_id == org.organization_id)
        .order_by(Lead.created_at.desc())
        .limit(limit)
    )
    if status_filter:
        stmt = stmt.where(Lead.status == status_filter)
    if source:
        stmt = stmt.where(Lead.source == source)
    if campaign_id:
        stmt = stmt.where(Lead.campaign_id == campaign_id)
    if product_id:
        stmt = stmt.where(Lead.product_id == product_id)
    if brand_id:
        stmt = stmt.where(Lead.brand_id == brand_id)
    if content_item_id:
        stmt = stmt.where(Lead.content_item_id == content_item_id)
    if tracking_link_id:
        stmt = stmt.where(Lead.tracking_link_id == tracking_link_id)
    if q:
        pat = f"%{q.lower()}%"
        if org.membership.role.value in ("ANALYST", "VIEWER"):
            stmt = stmt.where(or_(Lead.first_name.ilike(pat), Lead.last_name.ilike(pat)))
        else:
            stmt = stmt.where(
                or_(
                    Lead.first_name.ilike(pat),
                    Lead.last_name.ilike(pat),
                    Lead.email.ilike(pat),
                    Lead.phone.ilike(pat),
                    Lead.whatsapp.ilike(pat),
                )
            )
    return [serialize_lead_for_role(r, org.membership.role) for r in db.execute(stmt).scalars().all()]


@router.post("", response_model=LeadRead, status_code=201)
def create_lead(
    payload: LeadCreate,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_lead_write),
    db: Session = Depends(get_session),
) -> LeadRead:
    _validate_relations(
        db,
        org.organization_id,
        brand_id=payload.brand_id,
        product_id=payload.product_id,
        campaign_id=payload.campaign_id,
        content_item_id=payload.content_item_id,
        tracking_link_id=payload.tracking_link_id,
    )
    phone, whatsapp = _normalize_contact_fields(
        db, org.organization_id, payload.phone, payload.whatsapp
    )
    row = Lead(
        organization_id=org.organization_id,
        public_id=make_public_id("ld"),
        brand_id=payload.brand_id,
        product_id=payload.product_id,
        campaign_id=payload.campaign_id,
        content_item_id=payload.content_item_id,
        tracking_link_id=payload.tracking_link_id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=payload.email,
        phone=phone,
        whatsapp=whatsapp,
        source=payload.source,
        status=payload.status,
        country=payload.country,
        city=payload.city,
        notes=payload.notes,
        utm_source=payload.utm_source,
        utm_medium=payload.utm_medium,
        utm_campaign=payload.utm_campaign,
        utm_content=payload.utm_content,
        utm_term=payload.utm_term,
        external_id=payload.external_id,
        source_system=payload.source_system,
    )
    db.add(row)
    db.flush()
    _log_activity(
        db,
        org_id=org.organization_id,
        lead_id=row.id,
        actor_user_id=user.id,
        activity_type=LeadActivityType.CREATED,
        description="Lead created",
        metadata={"source": row.source.value},
    )
    audit.record(
        db,
        action="lead.created",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="lead",
        target_id=row.id,
        payload={"public_id": row.public_id, "source": row.source.value},
        request=request,
    )

    from app.automation.engine import TriggerContext, run_triggers
    from app.models.enums import AutomationTriggerType

    run_triggers(
        db,
        organization_id=org.organization_id,
        trigger_type=AutomationTriggerType.LEAD_CREATED,
        context=TriggerContext(
            brand_id=row.brand_id,
            campaign_id=row.campaign_id,
            product_id=row.product_id,
            lead_id=row.id,
            actor_user_id=user.id,
        ),
        request=request,
    )

    db.commit()
    db.refresh(row)
    return LeadRead.model_validate(row)


@router.get("/export")
def export_leads(
    status_filter: LeadStatus | None = Query(default=None, alias="status"),
    source: LeadSource | None = None,
    campaign_id: uuid.UUID | None = None,
    request: Request = None,  # type: ignore[assignment]
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_lead_export),
    db: Session = Depends(get_session),
) -> StreamingResponse:
    stmt = (
        select(Lead)
        .where(Lead.organization_id == org.organization_id)
        .order_by(Lead.created_at.desc())
    )
    if status_filter:
        stmt = stmt.where(Lead.status == status_filter)
    if source:
        stmt = stmt.where(Lead.source == source)
    if campaign_id:
        stmt = stmt.where(Lead.campaign_id == campaign_id)

    rows = db.execute(stmt).scalars().all()

    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_ALL)
    writer.writerow(
        [
            "public_id",
            "first_name",
            "last_name",
            "email",
            "phone",
            "whatsapp",
            "source",
            "status",
            "country",
            "city",
            "campaign_id",
            "content_item_id",
            "tracking_link_id",
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "utm_content",
            "utm_term",
            "created_at",
        ]
    )
    dangerous = ("=", "+", "-", "@", "\t", "\r")
    for r in rows:
        def clean(v):
            if v is None:
                return ""
            s = str(v)
            if s and s[0] in dangerous:
                s = "'" + s
            return s

        writer.writerow(
            [
                clean(r.public_id),
                clean(r.first_name),
                clean(r.last_name),
                clean(r.email),
                clean(r.phone),
                clean(r.whatsapp),
                clean(r.source.value if r.source else None),
                clean(r.status.value if r.status else None),
                clean(r.country),
                clean(r.city),
                clean(r.campaign_id),
                clean(r.content_item_id),
                clean(r.tracking_link_id),
                clean(r.utm_source),
                clean(r.utm_medium),
                clean(r.utm_campaign),
                clean(r.utm_content),
                clean(r.utm_term),
                clean(r.created_at.isoformat() if r.created_at else None),
            ]
        )

    audit.record(
        db,
        action="lead.exported",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="lead_export",
        target_id=None,
        payload={"row_count": len(rows)},
        request=request,
    )
    db.commit()

    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.read()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="leads.csv"'},
    )


@router.get("/{lead_id}", response_model=LeadRead)
def get_lead(
    lead_id: uuid.UUID,
    org: OrgContext = Depends(current_org),
    db: Session = Depends(get_session),
) -> LeadRead:
    return serialize_lead_for_role(_get_or_404(db, org.organization_id, lead_id), org.membership.role)


@router.patch("/{lead_id}", response_model=LeadRead)
def update_lead(
    lead_id: uuid.UUID,
    payload: LeadUpdate,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_lead_write),
    db: Session = Depends(get_session),
) -> LeadRead:
    row = _get_or_404(db, org.organization_id, lead_id)
    data = payload.model_dump(exclude_unset=True)
    if any(k in data for k in ("brand_id", "product_id", "campaign_id", "content_item_id")):
        _validate_relations(
            db,
            org.organization_id,
            brand_id=data.get("brand_id", row.brand_id),
            product_id=data.get("product_id", row.product_id),
            campaign_id=data.get("campaign_id", row.campaign_id),
            content_item_id=data.get("content_item_id", row.content_item_id),
            tracking_link_id=row.tracking_link_id,
        )
    if "phone" in data or "whatsapp" in data:
        phone, whatsapp = _normalize_contact_fields(
            db,
            org.organization_id,
            data.get("phone", row.phone),
            data.get("whatsapp", row.whatsapp),
        )
        if "phone" in data:
            data["phone"] = phone
        if "whatsapp" in data:
            data["whatsapp"] = whatsapp
    for k, v in data.items():
        setattr(row, k, v)
    db.flush()
    audit.record(
        db,
        action="lead.updated",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="lead",
        target_id=row.id,
        payload={"fields": list(data.keys())},
        request=request,
    )
    db.commit()
    db.refresh(row)
    return LeadRead.model_validate(row)


@router.delete("/{lead_id}", status_code=204)
def archive_lead(
    lead_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_lead_write),
    db: Session = Depends(get_session),
) -> None:
    row = _get_or_404(db, org.organization_id, lead_id)
    if row.status != LeadStatus.ARCHIVED:
        old = row.status
        row.status = LeadStatus.ARCHIVED
        db.flush()
        _log_activity(
            db,
            org_id=org.organization_id,
            lead_id=row.id,
            actor_user_id=user.id,
            activity_type=LeadActivityType.STATUS_CHANGED,
            description="Archived",
            metadata={"from": old.value, "to": LeadStatus.ARCHIVED.value},
        )
        audit.record(
            db,
            action="lead.updated",
            actor_user_id=user.id,
            organization_id=org.organization_id,
            target_type="lead",
            target_id=row.id,
            payload={"archived": True},
            request=request,
        )
    db.commit()
    return None


@router.post("/import", response_model=LeadRead)
def import_lead(
    payload: LeadImport,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_lead_write),
    db: Session = Depends(get_session),
) -> LeadRead:
    _validate_relations(
        db,
        org.organization_id,
        brand_id=payload.brand_id,
        product_id=payload.product_id,
        campaign_id=payload.campaign_id,
        content_item_id=payload.content_item_id,
        tracking_link_id=payload.tracking_link_id,
    )
    phone, whatsapp = _normalize_contact_fields(
        db, org.organization_id, payload.phone, payload.whatsapp
    )

    existing = db.execute(
        select(Lead).where(
            Lead.organization_id == org.organization_id,
            Lead.source_system == payload.source_system,
            Lead.external_id == payload.external_id,
        )
    ).scalar_one_or_none()

    if existing is not None:
        for field in (
            "first_name",
            "last_name",
            "email",
            "country",
            "city",
            "notes",
            "brand_id",
            "product_id",
            "campaign_id",
            "content_item_id",
            "tracking_link_id",
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "utm_content",
            "utm_term",
        ):
            v = getattr(payload, field)
            if v is not None:
                setattr(existing, field, v)
        if phone is not None:
            existing.phone = phone
        if whatsapp is not None:
            existing.whatsapp = whatsapp
        db.flush()
        audit.record(
            db,
            action="lead.imported",
            actor_user_id=user.id,
            organization_id=org.organization_id,
            target_type="lead",
            target_id=existing.id,
            payload={"external_id": payload.external_id, "operation": "upsert"},
            request=request,
        )
        db.commit()
        db.refresh(existing)
        return LeadRead.model_validate(existing)

    row = Lead(
        organization_id=org.organization_id,
        public_id=make_public_id("ld"),
        brand_id=payload.brand_id,
        product_id=payload.product_id,
        campaign_id=payload.campaign_id,
        content_item_id=payload.content_item_id,
        tracking_link_id=payload.tracking_link_id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=payload.email,
        phone=phone,
        whatsapp=whatsapp,
        source=payload.source,
        status=payload.status,
        country=payload.country,
        city=payload.city,
        notes=payload.notes,
        utm_source=payload.utm_source,
        utm_medium=payload.utm_medium,
        utm_campaign=payload.utm_campaign,
        utm_content=payload.utm_content,
        utm_term=payload.utm_term,
        external_id=payload.external_id,
        source_system=payload.source_system,
    )
    db.add(row)
    db.flush()
    _log_activity(
        db,
        org_id=org.organization_id,
        lead_id=row.id,
        actor_user_id=user.id,
        activity_type=LeadActivityType.IMPORTED,
        description=f"Imported from {payload.source_system.value}",
        metadata={"external_id": payload.external_id},
    )
    audit.record(
        db,
        action="lead.imported",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="lead",
        target_id=row.id,
        payload={
            "external_id": payload.external_id,
            "source_system": payload.source_system.value,
            "operation": "create",
        },
        request=request,
    )
    db.commit()
    db.refresh(row)
    return LeadRead.model_validate(row)


_STATUS_ACTIVITY_MAP = {
    LeadStatus.WON: LeadActivityType.WON,
    LeadStatus.LOST: LeadActivityType.LOST,
}


@router.post("/{lead_id}/status", response_model=LeadRead)
def change_status(
    lead_id: uuid.UUID,
    payload: LeadStatusChangeRequest,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_lead_write),
    db: Session = Depends(get_session),
) -> LeadRead:
    row = _get_or_404(db, org.organization_id, lead_id)
    if row.status == payload.status:
        return LeadRead.model_validate(row)
    old = row.status
    row.status = payload.status
    db.flush()
    _log_activity(
        db,
        org_id=org.organization_id,
        lead_id=row.id,
        actor_user_id=user.id,
        activity_type=_STATUS_ACTIVITY_MAP.get(
            payload.status, LeadActivityType.STATUS_CHANGED
        ),
        description=payload.note or f"Status {old.value} → {payload.status.value}",
        metadata={"from": old.value, "to": payload.status.value},
    )
    audit.record(
        db,
        action="lead.status_changed",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="lead",
        target_id=row.id,
        payload={"from": old.value, "to": payload.status.value},
        request=request,
    )

    from app.automation.engine import TriggerContext, run_triggers
    from app.models.enums import AutomationTriggerType

    run_triggers(
        db,
        organization_id=org.organization_id,
        trigger_type=AutomationTriggerType.LEAD_STATUS_CHANGED,
        context=TriggerContext(
            brand_id=row.brand_id,
            campaign_id=row.campaign_id,
            product_id=row.product_id,
            lead_id=row.id,
            actor_user_id=user.id,
            extra={"status": payload.status.value},
        ),
        request=request,
    )

    db.commit()
    db.refresh(row)
    return LeadRead.model_validate(row)


@router.get("/{lead_id}/activities", response_model=list[LeadActivityRead])
def list_activities(
    lead_id: uuid.UUID,
    org: OrgContext = Depends(current_org),
    db: Session = Depends(get_session),
) -> list[LeadActivityRead]:
    _get_or_404(db, org.organization_id, lead_id)
    rows = (
        db.execute(
            select(LeadActivity)
            .where(
                LeadActivity.organization_id == org.organization_id,
                LeadActivity.lead_id == lead_id,
            )
            .order_by(LeadActivity.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [
        sanitize_lead_activity(
            LeadActivityRead(
                id=r.id,
                public_id=r.public_id,
                lead_id=r.lead_id,
                actor_user_id=r.actor_user_id,
                activity_type=r.activity_type,
                description=r.description,
                metadata=r.activity_metadata,
                created_at=r.created_at,
            ),
            org.membership.role,
        )
        for r in rows
    ]


@router.post("/{lead_id}/activities", response_model=LeadActivityRead, status_code=201)
def create_activity(
    lead_id: uuid.UUID,
    payload: LeadActivityCreate,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_lead_write),
    db: Session = Depends(get_session),
) -> LeadActivityRead:
    _get_or_404(db, org.organization_id, lead_id)
    row = _log_activity(
        db,
        org_id=org.organization_id,
        lead_id=lead_id,
        actor_user_id=user.id,
        activity_type=payload.activity_type,
        description=payload.description,
        metadata=payload.metadata,
    )
    audit.record(
        db,
        action="lead.activity_added",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="lead_activity",
        target_id=row.id,
        payload={"activity_type": payload.activity_type.value},
        request=request,
    )
    db.commit()
    db.refresh(row)
    return LeadActivityRead(
        id=row.id,
        public_id=row.public_id,
        lead_id=row.lead_id,
        actor_user_id=row.actor_user_id,
        activity_type=row.activity_type,
        description=row.description,
        metadata=row.activity_metadata,
        created_at=row.created_at,
    )
