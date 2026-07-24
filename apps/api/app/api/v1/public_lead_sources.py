from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.deps import OrgContext, current_org, current_user, get_session, require_public_source_write
from app.models.ai import PublicLeadSource
from app.models.brand import Brand
from app.models.campaign import Campaign
from app.models.product import Product
from app.models.user import User
from app.schemas.ai import PublicLeadSourceCreate, PublicLeadSourceRead, PublicLeadSourceUpdate
from app.utils.public_id import make as make_public_id
from app.utils.public_token import generate as generate_token

router = APIRouter(prefix="/public-lead-sources", tags=["public-lead-sources"])


def _get_or_404(db: Session, org_id: uuid.UUID, source_id: uuid.UUID) -> PublicLeadSource:
    row = db.execute(
        select(PublicLeadSource).where(
            PublicLeadSource.id == source_id, PublicLeadSource.organization_id == org_id
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="public lead source not found")
    return row


def _validate_fks(
    db: Session,
    org_id: uuid.UUID,
    brand_id: uuid.UUID | None,
    product_id: uuid.UUID | None,
    campaign_id: uuid.UUID | None,
) -> None:
    for model, val, label in (
        (Brand, brand_id, "brand"),
        (Product, product_id, "product"),
        (Campaign, campaign_id, "campaign"),
    ):
        if val is None:
            continue
        ok = db.execute(
            select(model.id).where(model.id == val, model.organization_id == org_id)
        ).scalar_one_or_none()
        if ok is None:
            raise HTTPException(
                status_code=400, detail=f"{label} not found in organization"
            )


@router.get("", response_model=list[PublicLeadSourceRead])
def list_sources(
    org: OrgContext = Depends(current_org),
    db: Session = Depends(get_session),
) -> list[PublicLeadSourceRead]:
    rows = db.execute(
        select(PublicLeadSource)
        .where(PublicLeadSource.organization_id == org.organization_id)
        .order_by(PublicLeadSource.created_at.desc())
    ).scalars().all()
    return [PublicLeadSourceRead.model_validate(r) for r in rows]


@router.post("", response_model=PublicLeadSourceRead, status_code=201)
def create_source(
    payload: PublicLeadSourceCreate,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_public_source_write),
    db: Session = Depends(get_session),
) -> PublicLeadSourceRead:
    _validate_fks(db, org.organization_id, payload.brand_id, payload.product_id, payload.campaign_id)
    row = PublicLeadSource(
        organization_id=org.organization_id,
        public_id=make_public_id("pls"),
        brand_id=payload.brand_id,
        product_id=payload.product_id,
        campaign_id=payload.campaign_id,
        name=payload.name,
        public_token=generate_token(),
        allowed_origins=payload.allowed_origins,
        expires_at=payload.expires_at,
        default_utm_source=payload.default_utm_source,
        default_utm_medium=payload.default_utm_medium,
        default_utm_campaign=payload.default_utm_campaign,
    )
    db.add(row)
    db.flush()
    audit.record(
        db,
        action="public_lead_source.created",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="public_lead_source",
        target_id=row.id,
        payload={"public_id": row.public_id, "name": row.name},
        request=request,
    )
    db.commit()
    db.refresh(row)
    return PublicLeadSourceRead.model_validate(row)


@router.patch("/{source_id}", response_model=PublicLeadSourceRead)
def update_source(
    source_id: uuid.UUID,
    payload: PublicLeadSourceUpdate,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_public_source_write),
    db: Session = Depends(get_session),
) -> PublicLeadSourceRead:
    row = _get_or_404(db, org.organization_id, source_id)
    data = payload.model_dump(exclude_unset=True)
    if any(k in data for k in ("brand_id", "product_id", "campaign_id")):
        _validate_fks(
            db,
            org.organization_id,
            data.get("brand_id", row.brand_id),
            data.get("product_id", row.product_id),
            data.get("campaign_id", row.campaign_id),
        )
    for k, v in data.items():
        setattr(row, k, v)
    db.flush()
    audit.record(
        db,
        action="public_lead_source.updated",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="public_lead_source",
        target_id=row.id,
        payload={"fields": list(data.keys())},
        request=request,
    )
    db.commit()
    db.refresh(row)
    return PublicLeadSourceRead.model_validate(row)


@router.post("/{source_id}/rotate-token", response_model=PublicLeadSourceRead)
def rotate_token(
    source_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_public_source_write),
    db: Session = Depends(get_session),
) -> PublicLeadSourceRead:
    row = _get_or_404(db, org.organization_id, source_id)
    row.public_token = generate_token()
    db.flush()
    audit.record(
        db,
        action="public_lead_source.token_rotated",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="public_lead_source",
        target_id=row.id,
        payload={},
        request=request,
    )
    db.commit()
    db.refresh(row)
    return PublicLeadSourceRead.model_validate(row)


@router.post("/{source_id}/deactivate", response_model=PublicLeadSourceRead)
def deactivate_source(
    source_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_public_source_write),
    db: Session = Depends(get_session),
) -> PublicLeadSourceRead:
    row = _get_or_404(db, org.organization_id, source_id)
    row.is_active = False
    db.flush()
    audit.record(
        db,
        action="public_lead_source.deactivated",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="public_lead_source",
        target_id=row.id,
        payload={},
        request=request,
    )
    db.commit()
    db.refresh(row)
    return PublicLeadSourceRead.model_validate(row)
