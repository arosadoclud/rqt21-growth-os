from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
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


def _get_or_create_schedule(db: Session, org_id: uuid.UUID, brand_id: uuid.UUID) -> StorySchedule:
    """Created lazily (disabled, default settings) the first time a user
    opens the Historias screen for a brand — see app.models.story for the
    "never active until a human opts in" rationale. One row per brand —
    it fans out to every platform (Facebook, Instagram) that has a
    connection configured, all from the same daily batch/photo upload."""
    row = db.execute(
        select(StorySchedule).where(
            StorySchedule.organization_id == org_id, StorySchedule.brand_id == brand_id
        )
    ).scalar_one_or_none()
    if row is None:
        row = StorySchedule(
            organization_id=org_id,
            public_id=make_public_id("sts"),
            brand_id=brand_id,
        )
        db.add(row)
        db.flush()
    return row


def _validate_connection(db: Session, org_id: uuid.UUID, connection_id: uuid.UUID | None, platform: Platform) -> None:
    if connection_id is None:
        return
    connection = db.execute(
        select(PublishingConnection).where(
            PublishingConnection.id == connection_id,
            PublishingConnection.organization_id == org_id,
        )
    ).scalar_one_or_none()
    if connection is None:
        raise HTTPException(status_code=400, detail=f"{platform.value} connection not found in organization")
    if connection.platform != platform:
        raise HTTPException(
            status_code=400,
            detail=f"the {platform.value.lower()} connection's platform does not match",
        )


@router.get("/{brand_id}", response_model=StoryConfigRead)
def get_story_config(
    brand_id: uuid.UUID,
    org: OrgContext = Depends(current_org),
    db: Session = Depends(get_session),
) -> StoryConfigRead:
    _brand_or_404(db, org.organization_id, brand_id)
    row = _get_or_create_schedule(db, org.organization_id, brand_id)
    db.commit()
    db.refresh(row)
    return StoryConfigRead.model_validate(row)


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
    _validate_connection(db, org.organization_id, payload.facebook_connection_id, Platform.FACEBOOK)
    _validate_connection(db, org.organization_id, payload.instagram_connection_id, Platform.INSTAGRAM)

    row = _get_or_create_schedule(db, org.organization_id, brand_id)
    row.facebook_connection_id = payload.facebook_connection_id
    row.instagram_connection_id = payload.instagram_connection_id
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
            "facebook_connection_id": str(row.facebook_connection_id) if row.facebook_connection_id else None,
            "instagram_connection_id": str(row.instagram_connection_id) if row.instagram_connection_id else None,
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
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_story_admin),
    db: Session = Depends(get_session),
) -> StoryConfigRead:
    """Generate today's full batch of story copy right away (up to
    max_per_day stories, one every interval_minutes apart starting now) —
    only if it hasn't already run today. Each approved story gets a
    scheduled publish slot per configured platform; "pending-photos" (see
    below) is where a human uploads each one's photo, which is what
    actually publishes it to every configured platform at once."""
    _brand_or_404(db, org.organization_id, brand_id)
    row = _get_or_create_schedule(db, org.organization_id, brand_id)
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
    (which pre-creates one DRAFT Publication per configured platform, all
    sharing the same scheduled_for slot) and the upload hook in
    app.api.v1.assets.complete_upload, which fans out the publish (or
    schedule) to every one of them the moment a matching photo lands. A
    content item can now have more than one Publication (one per
    platform) — MIN(scheduled_for) collapses them back to one row per
    content since they all share the same slot time by construction."""
    _brand_or_404(db, org.organization_id, brand_id)
    photo_attached = (
        select(Asset.content_item_id).where(Asset.content_item_id.is_not(None)).distinct()
    )
    slot_by_content = (
        select(
            Publication.content_item_id.label("content_item_id"),
            func.min(Publication.scheduled_for).label("scheduled_for"),
        )
        .group_by(Publication.content_item_id)
        .subquery()
    )
    rows = (
        db.execute(
            select(ContentItem, slot_by_content.c.scheduled_for)
            .outerjoin(slot_by_content, slot_by_content.c.content_item_id == ContentItem.id)
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
