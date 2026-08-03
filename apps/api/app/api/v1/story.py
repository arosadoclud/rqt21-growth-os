from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.deps import (
    OrgContext,
    current_org,
    current_user,
    get_session,
    require_story_admin,
)
from app.models.assets import Asset
from app.models.brand import Brand
from app.models.content import ContentItem
from app.models.enums import Platform, ReviewStatus, SourceSystem
from app.models.publishing import Publication, PublishingConnection
from app.models.story import StorySchedule
from app.models.user import User
from app.schemas.growth import ContentRead
from app.schemas.story import StoryConfigRead, StoryConfigWrite, StoryPendingPhoto
from app.utils.public_id import make as make_public_id

router = APIRouter(prefix="/story-config", tags=["story"])


def _brand_or_404(db: Session, org_id: uuid.UUID, brand_id: uuid.UUID) -> Brand:
    b = db.execute(
        select(Brand).where(Brand.id == brand_id, Brand.organization_id == org_id)
    ).scalar_one_or_none()
    if b is None:
        raise HTTPException(status_code=404, detail="brand not found")
    return b


def _get_or_create_schedule(
    db: Session, org_id: uuid.UUID, brand_id: uuid.UUID, platform: Platform
) -> StorySchedule:
    """Created lazily (disabled, default settings) the first time a user
    opens the Historias screen for a brand+platform — see app.models.story
    for the "never active until a human opts in" rationale, and for why
    there can be more than one row per brand (one per platform)."""
    row = db.execute(
        select(StorySchedule).where(
            StorySchedule.organization_id == org_id,
            StorySchedule.brand_id == brand_id,
            StorySchedule.platform == platform.value,
        )
    ).scalar_one_or_none()
    if row is None:
        row = StorySchedule(
            organization_id=org_id,
            public_id=make_public_id("sts"),
            brand_id=brand_id,
            platform=platform.value,
        )
        db.add(row)
        db.flush()
    return row


@router.get("/{brand_id}", response_model=StoryConfigRead)
def get_story_config(
    brand_id: uuid.UUID,
    platform: Platform = Query(Platform.INSTAGRAM),
    org: OrgContext = Depends(current_org),
    db: Session = Depends(get_session),
) -> StoryConfigRead:
    _brand_or_404(db, org.organization_id, brand_id)
    row = _get_or_create_schedule(db, org.organization_id, brand_id, platform)
    db.commit()
    db.refresh(row)
    return StoryConfigRead.model_validate(row)


@router.get("/{brand_id}/list", response_model=list[StoryConfigRead])
def list_story_configs(
    brand_id: uuid.UUID,
    org: OrgContext = Depends(current_org),
    db: Session = Depends(get_session),
) -> list[StoryConfigRead]:
    """Every Historias schedule for this brand, one per platform that has
    ever been configured (Facebook and Instagram can run at the same
    time) — used by the /stories screen to render one config card per
    platform instead of assuming a single schedule per brand."""
    _brand_or_404(db, org.organization_id, brand_id)
    rows = (
        db.execute(
            select(StorySchedule)
            .where(
                StorySchedule.organization_id == org.organization_id,
                StorySchedule.brand_id == brand_id,
            )
            .order_by(StorySchedule.platform.asc())
        )
        .scalars()
        .all()
    )
    return [StoryConfigRead.model_validate(row) for row in rows]


@router.put("/{brand_id}", response_model=StoryConfigRead)
def update_story_config(
    brand_id: uuid.UUID,
    payload: StoryConfigWrite,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_story_admin),
    db: Session = Depends(get_session),
) -> StoryConfigRead:
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

    row = _get_or_create_schedule(db, org.organization_id, brand_id, payload.platform)
    row.publishing_connection_id = payload.publishing_connection_id
    row.enabled = payload.enabled
    row.interval_minutes = payload.interval_minutes
    row.max_per_day = payload.max_per_day
    db.flush()

    audit.record(
        db,
        action="story_config.updated",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="story_schedule",
        target_id=row.id,
        payload={
            "enabled": row.enabled,
            "interval_minutes": row.interval_minutes,
            "max_per_day": row.max_per_day,
            "platform": row.platform,
        },
        request=request,
    )
    db.commit()
    db.refresh(row)
    return StoryConfigRead.model_validate(row)


@router.post("/{brand_id}/run-now", response_model=StoryConfigRead)
def run_story_now(
    brand_id: uuid.UUID,
    request: Request,
    platform: Platform = Query(Platform.INSTAGRAM),
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_story_admin),
    db: Session = Depends(get_session),
) -> StoryConfigRead:
    """Generate today's full batch of story copy right away (up to
    max_per_day stories, one every interval_minutes apart starting now) —
    only if it hasn't already run today. Each approved story gets a
    scheduled publish slot; "pending-photos" (see below) is where a human
    uploads each one's photo, which is what actually publishes it."""
    _brand_or_404(db, org.organization_id, brand_id)
    row = _get_or_create_schedule(db, org.organization_id, brand_id, platform)
    if not row.enabled:
        raise HTTPException(
            status_code=400, detail="enable the story cycle before generating manually"
        )
    db.commit()
    schedule_id = row.id

    from app.workers.story_scheduler import run_now as _worker_run_now

    outcome = _worker_run_now(schedule_id)
    if outcome is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "today's batch was already generated (or generation failed, or "
                "a run is already in progress) — check pending-photos"
            ),
        )

    audit.record(
        db,
        action="story_config.run_now",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="story_schedule",
        target_id=schedule_id,
        payload=outcome,
        request=request,
    )
    db.commit()

    db.expire_all()
    fresh = db.get(StorySchedule, schedule_id)
    return StoryConfigRead.model_validate(fresh)


@router.get("/{brand_id}/pending-photos", response_model=list[StoryPendingPhoto])
def list_story_pending_photos(
    brand_id: uuid.UUID,
    org: OrgContext = Depends(current_org),
    db: Session = Depends(get_session),
) -> list[StoryPendingPhoto]:
    """Approved story copy still waiting on a human to upload its photo,
    ordered by its scheduled publish slot — see app.workers.story_scheduler
    (which pre-creates a DRAFT Publication with scheduled_for for each
    one, if a connection is configured) and the upload hook in
    app.api.v1.assets.complete_upload, which publishes (or schedules) the
    moment a matching photo lands on one of these."""
    _brand_or_404(db, org.organization_id, brand_id)
    photo_attached = (
        select(Asset.content_item_id).where(Asset.content_item_id.is_not(None)).distinct()
    )
    rows = (
        db.execute(
            select(ContentItem, Publication.scheduled_for)
            .outerjoin(Publication, Publication.content_item_id == ContentItem.id)
            .where(
                ContentItem.organization_id == org.organization_id,
                ContentItem.brand_id == brand_id,
                ContentItem.source_system == SourceSystem.STORY_AUTO,
                ContentItem.review_status == ReviewStatus.APPROVED,
                ContentItem.id.not_in(photo_attached),
            )
            .order_by(ContentItem.created_at.asc())
            .limit(100)
        )
        .all()
    )
    return [
        StoryPendingPhoto(
            id=content.id,
            title=content.title,
            caption=content.caption,
            cta=content.cta,
            created_at=content.created_at,
            scheduled_for=scheduled_for,
        )
        for content, scheduled_for in rows
    ]


@router.get("/{brand_id}/history", response_model=list[ContentRead])
def list_story_history(
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
                ContentItem.source_system == SourceSystem.STORY_AUTO,
            )
            .order_by(ContentItem.created_at.desc())
            .limit(100)
        )
        .scalars()
        .all()
    )
    return [ContentRead.model_validate(r) for r in rows]
