from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.deps import (
    OrgContext,
    current_org,
    current_user,
    get_session,
    require_headline_admin,
)
from app.models.brand import Brand
from app.models.content import ContentItem
from app.models.enums import SourceSystem
from app.models.headline import HeadlineSchedule
from app.models.publishing import PublishingConnection
from app.models.user import User
from app.schemas.growth import ContentRead
from app.schemas.headline import HeadlineConfigRead, HeadlineConfigWrite
from app.utils.public_id import make as make_public_id

router = APIRouter(prefix="/headline-config", tags=["headline"])


def _brand_or_404(db: Session, org_id: uuid.UUID, brand_id: uuid.UUID) -> Brand:
    b = db.execute(
        select(Brand).where(Brand.id == brand_id, Brand.organization_id == org_id)
    ).scalar_one_or_none()
    if b is None:
        raise HTTPException(status_code=404, detail="brand not found")
    return b


def _get_or_create_schedule(db: Session, org_id: uuid.UUID, brand_id: uuid.UUID) -> HeadlineSchedule:
    """Created lazily (disabled, default settings) the first time a user
    opens the Headline screen for a brand — see app.models.headline for
    the "never active until a human opts in" rationale."""
    row = db.execute(
        select(HeadlineSchedule).where(
            HeadlineSchedule.organization_id == org_id, HeadlineSchedule.brand_id == brand_id
        )
    ).scalar_one_or_none()
    if row is None:
        row = HeadlineSchedule(
            organization_id=org_id,
            public_id=make_public_id("hls"),
            brand_id=brand_id,
        )
        db.add(row)
        db.flush()
    return row


@router.get("/{brand_id}", response_model=HeadlineConfigRead)
def get_headline_config(
    brand_id: uuid.UUID,
    org: OrgContext = Depends(current_org),
    db: Session = Depends(get_session),
) -> HeadlineConfigRead:
    _brand_or_404(db, org.organization_id, brand_id)
    row = _get_or_create_schedule(db, org.organization_id, brand_id)
    db.commit()
    db.refresh(row)
    return HeadlineConfigRead.model_validate(row)


@router.put("/{brand_id}", response_model=HeadlineConfigRead)
def update_headline_config(
    brand_id: uuid.UUID,
    payload: HeadlineConfigWrite,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_headline_admin),
    db: Session = Depends(get_session),
) -> HeadlineConfigRead:
    _brand_or_404(db, org.organization_id, brand_id)

    if payload.publishing_connection_id is not None:
        connection = db.execute(
            select(PublishingConnection).where(
                PublishingConnection.id == payload.publishing_connection_id,
                PublishingConnection.organization_id == org.organization_id,
            )
        ).scalar_one_or_none()
        if connection is None:
            raise HTTPException(
                status_code=400, detail="publishing connection not found in organization"
            )
        if connection.platform.value != payload.platform.value:
            raise HTTPException(
                status_code=400,
                detail="the connection's platform does not match the requested platform",
            )

    row = _get_or_create_schedule(db, org.organization_id, brand_id)
    row.publishing_connection_id = payload.publishing_connection_id
    row.platform = payload.platform.value
    row.enabled = payload.enabled
    row.interval_hours = payload.interval_hours
    row.max_per_day = payload.max_per_day
    db.flush()

    audit.record(
        db,
        action="headline_config.updated",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="headline_schedule",
        target_id=row.id,
        payload={
            "enabled": row.enabled,
            "interval_hours": row.interval_hours,
            "max_per_day": row.max_per_day,
            "platform": row.platform,
        },
        request=request,
    )
    db.commit()
    db.refresh(row)
    return HeadlineConfigRead.model_validate(row)


@router.post("/{brand_id}/run-now", response_model=HeadlineConfigRead)
def run_headline_now(
    brand_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_headline_admin),
    db: Session = Depends(get_session),
) -> HeadlineConfigRead:
    """Generate (and, if auto-approved, publish) one headline post right
    away — bypasses interval_hours but still enforces max_per_day and the
    same auto-approval gate as the regular scheduled sweep."""
    _brand_or_404(db, org.organization_id, brand_id)
    row = _get_or_create_schedule(db, org.organization_id, brand_id)
    if not row.enabled:
        raise HTTPException(
            status_code=400, detail="enable the headline cycle before generating manually"
        )
    db.commit()
    schedule_id = row.id

    from app.workers.headline_scheduler import run_now as _worker_run_now

    outcome = _worker_run_now(schedule_id)
    if outcome == "skipped":
        raise HTTPException(
            status_code=409,
            detail=(
                "could not generate right now (daily limit reached, generation "
                "failed, or a run is already in progress)"
            ),
        )

    audit.record(
        db,
        action="headline_config.run_now",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="headline_schedule",
        target_id=schedule_id,
        payload={"outcome": outcome},
        request=request,
    )
    db.commit()

    db.expire_all()
    fresh = db.get(HeadlineSchedule, schedule_id)
    return HeadlineConfigRead.model_validate(fresh)


@router.get("/{brand_id}/history", response_model=list[ContentRead])
def list_headline_history(
    brand_id: uuid.UUID,
    org: OrgContext = Depends(current_org),
    db: Session = Depends(get_session),
) -> list[ContentRead]:
    _brand_or_404(db, org.organization_id, brand_id)
    rows = (
        db.execute(
            select(ContentItem)
            .where(
                ContentItem.organization_id == org.organization_id,
                ContentItem.brand_id == brand_id,
                ContentItem.source_system == SourceSystem.HEADLINE_AUTO,
            )
            .order_by(ContentItem.created_at.desc())
            .limit(100)
        )
        .scalars()
        .all()
    )
    return [ContentRead.model_validate(r) for r in rows]
