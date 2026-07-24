from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.deps import (
    OrgContext,
    current_org,
    current_user,
    get_session,
    require_editorial_write,
)
from app.models.brand import Brand
from app.models.campaign import Campaign
from app.models.content import ContentItem
from app.models.editorial import EditorialCalendarItem
from app.models.enums import EditorialPlatform, EditorialStatus, Priority
from app.models.membership import Membership
from app.models.product import Product
from app.models.user import User
from app.schemas.editorial import (
    EditorialItemCreate,
    EditorialItemRead,
    EditorialItemUpdate,
    MarkPublishedRequest,
    ScheduleRequest,
)
from app.utils.public_id import make as make_public_id

router = APIRouter(prefix="/editorial-calendar", tags=["editorial-calendar"])


def _get_or_404(db: Session, org_id: uuid.UUID, item_id: uuid.UUID) -> EditorialCalendarItem:
    row = db.execute(
        select(EditorialCalendarItem).where(
            EditorialCalendarItem.id == item_id,
            EditorialCalendarItem.organization_id == org_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="editorial item not found")
    return row


def _validate_fks(
    db: Session,
    org_id: uuid.UUID,
    *,
    content_item_id: uuid.UUID | None,
    brand_id: uuid.UUID | None,
    campaign_id: uuid.UUID | None,
    product_id: uuid.UUID | None,
    assigned_to_user_id: uuid.UUID | None,
) -> None:
    checks: list[tuple[type, uuid.UUID | None, str]] = [
        (ContentItem, content_item_id, "content_item"),
        (Brand, brand_id, "brand"),
        (Campaign, campaign_id, "campaign"),
        (Product, product_id, "product"),
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
    if assigned_to_user_id is not None:
        m = db.execute(
            select(Membership.id).where(
                Membership.user_id == assigned_to_user_id,
                Membership.organization_id == org_id,
            )
        ).scalar_one_or_none()
        if m is None:
            raise HTTPException(
                status_code=400, detail="assignee is not a member of this organization"
            )


def _serialize(row: EditorialCalendarItem) -> EditorialItemRead:
    return EditorialItemRead.model_validate(row)


def _apply_filters(stmt, params: dict):
    if params.get("status"):
        stmt = stmt.where(EditorialCalendarItem.status == params["status"])
    if params.get("platform"):
        stmt = stmt.where(EditorialCalendarItem.platform == params["platform"])
    if params.get("campaign_id"):
        stmt = stmt.where(EditorialCalendarItem.campaign_id == params["campaign_id"])
    if params.get("brand_id"):
        stmt = stmt.where(EditorialCalendarItem.brand_id == params["brand_id"])
    if params.get("product_id"):
        stmt = stmt.where(EditorialCalendarItem.product_id == params["product_id"])
    if params.get("assigned_to_user_id"):
        stmt = stmt.where(
            EditorialCalendarItem.assigned_to_user_id == params["assigned_to_user_id"]
        )
    if params.get("priority"):
        stmt = stmt.where(EditorialCalendarItem.priority == params["priority"])
    return stmt


@router.get("", response_model=list[EditorialItemRead])
def list_items(
    status_filter: EditorialStatus | None = Query(default=None, alias="status"),
    platform: EditorialPlatform | None = None,
    campaign_id: uuid.UUID | None = None,
    brand_id: uuid.UUID | None = None,
    product_id: uuid.UUID | None = None,
    assigned_to_user_id: uuid.UUID | None = None,
    priority: Priority | None = None,
    org: OrgContext = Depends(current_org),
    db: Session = Depends(get_session),
) -> list[EditorialItemRead]:
    stmt = (
        select(EditorialCalendarItem)
        .where(EditorialCalendarItem.organization_id == org.organization_id)
        .order_by(EditorialCalendarItem.scheduled_for.asc().nulls_last())
    )
    stmt = _apply_filters(
        stmt,
        dict(
            status=status_filter,
            platform=platform,
            campaign_id=campaign_id,
            brand_id=brand_id,
            product_id=product_id,
            assigned_to_user_id=assigned_to_user_id,
            priority=priority,
        ),
    )
    return [_serialize(r) for r in db.execute(stmt).scalars().all()]


@router.get("/range", response_model=list[EditorialItemRead])
def range_items(
    start: datetime = Query(...),
    end: datetime = Query(...),
    status_filter: EditorialStatus | None = Query(default=None, alias="status"),
    platform: EditorialPlatform | None = None,
    campaign_id: uuid.UUID | None = None,
    brand_id: uuid.UUID | None = None,
    org: OrgContext = Depends(current_org),
    db: Session = Depends(get_session),
) -> list[EditorialItemRead]:
    if end <= start:
        raise HTTPException(status_code=400, detail="end must be after start")
    stmt = (
        select(EditorialCalendarItem)
        .where(EditorialCalendarItem.organization_id == org.organization_id)
        .where(EditorialCalendarItem.scheduled_for.is_not(None))
        .where(EditorialCalendarItem.scheduled_for >= start)
        .where(EditorialCalendarItem.scheduled_for < end)
        .order_by(EditorialCalendarItem.scheduled_for.asc())
    )
    stmt = _apply_filters(
        stmt,
        dict(
            status=status_filter,
            platform=platform,
            campaign_id=campaign_id,
            brand_id=brand_id,
        ),
    )
    return [_serialize(r) for r in db.execute(stmt).scalars().all()]


@router.post("", response_model=EditorialItemRead, status_code=201)
def create_item(
    payload: EditorialItemCreate,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_editorial_write),
    db: Session = Depends(get_session),
) -> EditorialItemRead:
    _validate_fks(
        db,
        org.organization_id,
        content_item_id=payload.content_item_id,
        brand_id=payload.brand_id,
        campaign_id=payload.campaign_id,
        product_id=payload.product_id,
        assigned_to_user_id=payload.assigned_to_user_id,
    )
    if payload.status == EditorialStatus.SCHEDULED and payload.scheduled_for is None:
        raise HTTPException(
            status_code=400, detail="scheduled_for is required when status is SCHEDULED"
        )
    if payload.status == EditorialStatus.ARCHIVED:
        raise HTTPException(
            status_code=400, detail="cannot create an archived editorial item"
        )
    row = EditorialCalendarItem(
        organization_id=org.organization_id,
        public_id=make_public_id("eci"),
        content_item_id=payload.content_item_id,
        brand_id=payload.brand_id,
        campaign_id=payload.campaign_id,
        product_id=payload.product_id,
        assigned_to_user_id=payload.assigned_to_user_id,
        created_by_user_id=user.id,
        platform=payload.platform,
        content_format=payload.content_format,
        scheduled_for=payload.scheduled_for,
        timezone=payload.timezone,
        status=payload.status,
        priority=payload.priority,
        notes=payload.notes,
    )
    db.add(row)
    db.flush()
    audit.record(
        db,
        action="editorial_item.created",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="editorial_item",
        target_id=row.id,
        payload={"public_id": row.public_id, "status": row.status.value},
        request=request,
    )
    db.commit()
    db.refresh(row)
    return _serialize(row)


@router.get("/{item_id}", response_model=EditorialItemRead)
def get_item(
    item_id: uuid.UUID,
    org: OrgContext = Depends(current_org),
    db: Session = Depends(get_session),
) -> EditorialItemRead:
    return _serialize(_get_or_404(db, org.organization_id, item_id))


@router.patch("/{item_id}", response_model=EditorialItemRead)
def update_item(
    item_id: uuid.UUID,
    payload: EditorialItemUpdate,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_editorial_write),
    db: Session = Depends(get_session),
) -> EditorialItemRead:
    row = _get_or_404(db, org.organization_id, item_id)
    if row.status == EditorialStatus.ARCHIVED:
        raise HTTPException(status_code=400, detail="archived items cannot be edited")
    data = payload.model_dump(exclude_unset=True)
    if any(
        k in data
        for k in ("campaign_id", "product_id", "assigned_to_user_id")
    ):
        _validate_fks(
            db,
            org.organization_id,
            content_item_id=None,
            brand_id=None,
            campaign_id=data.get("campaign_id"),
            product_id=data.get("product_id"),
            assigned_to_user_id=data.get("assigned_to_user_id"),
        )
    new_status = data.get("status")
    if new_status == EditorialStatus.SCHEDULED:
        new_sched = data.get("scheduled_for", row.scheduled_for)
        if new_sched is None:
            raise HTTPException(
                status_code=400,
                detail="scheduled_for is required to move to SCHEDULED",
            )
    if new_status == EditorialStatus.ARCHIVED and row.status == EditorialStatus.PUBLISHED:
        raise HTTPException(
            status_code=400, detail="cannot archive a published item"
        )
    for k, v in data.items():
        setattr(row, k, v)
    db.flush()
    audit.record(
        db,
        action="editorial_item.updated",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="editorial_item",
        target_id=row.id,
        payload={"fields": list(data.keys())},
        request=request,
    )
    db.commit()
    db.refresh(row)
    return _serialize(row)


@router.delete("/{item_id}", status_code=204)
def delete_item(
    item_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_editorial_write),
    db: Session = Depends(get_session),
) -> None:
    row = _get_or_404(db, org.organization_id, item_id)
    # Published rows are preserved for historic trace: archive, not delete.
    if row.status == EditorialStatus.PUBLISHED:
        new_status = EditorialStatus.ARCHIVED
        action = "editorial_item.updated"
    else:
        new_status = EditorialStatus.CANCELLED
        action = "editorial_item.cancelled"
    row.status = new_status
    db.flush()
    audit.record(
        db,
        action=action,
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="editorial_item",
        target_id=row.id,
        payload={"new_status": new_status.value},
        request=request,
    )
    db.commit()
    return None


@router.post("/{item_id}/schedule", response_model=EditorialItemRead)
def schedule_item(
    item_id: uuid.UUID,
    payload: ScheduleRequest,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_editorial_write),
    db: Session = Depends(get_session),
) -> EditorialItemRead:
    row = _get_or_404(db, org.organization_id, item_id)
    if row.status in (EditorialStatus.PUBLISHED, EditorialStatus.ARCHIVED):
        raise HTTPException(
            status_code=400, detail="cannot schedule a published or archived item"
        )
    row.status = EditorialStatus.SCHEDULED
    row.scheduled_for = payload.scheduled_for
    row.timezone = payload.timezone
    db.flush()
    audit.record(
        db,
        action="editorial_item.scheduled",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="editorial_item",
        target_id=row.id,
        payload={"scheduled_for": payload.scheduled_for.isoformat()},
        request=request,
    )
    db.commit()
    db.refresh(row)
    return _serialize(row)


@router.post("/{item_id}/mark-published", response_model=EditorialItemRead)
def mark_published(
    item_id: uuid.UUID,
    payload: MarkPublishedRequest,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_editorial_write),
    db: Session = Depends(get_session),
) -> EditorialItemRead:
    row = _get_or_404(db, org.organization_id, item_id)
    if row.status == EditorialStatus.ARCHIVED:
        raise HTTPException(
            status_code=400, detail="cannot publish an archived item"
        )
    row.status = EditorialStatus.PUBLISHED
    row.publication_url = str(payload.publication_url)
    row.published_at = payload.published_at or datetime.now(UTC)
    db.flush()
    audit.record(
        db,
        action="editorial_item.published",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="editorial_item",
        target_id=row.id,
        payload={"publication_url": row.publication_url},
        request=request,
    )
    db.commit()
    db.refresh(row)
    return _serialize(row)


@router.post("/{item_id}/cancel", response_model=EditorialItemRead)
def cancel_item(
    item_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_editorial_write),
    db: Session = Depends(get_session),
) -> EditorialItemRead:
    row = _get_or_404(db, org.organization_id, item_id)
    if row.status == EditorialStatus.PUBLISHED:
        raise HTTPException(
            status_code=400, detail="cannot cancel a published item; archive instead"
        )
    row.status = EditorialStatus.CANCELLED
    db.flush()
    audit.record(
        db,
        action="editorial_item.cancelled",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="editorial_item",
        target_id=row.id,
        payload={},
        request=request,
    )
    db.commit()
    db.refresh(row)
    return _serialize(row)
