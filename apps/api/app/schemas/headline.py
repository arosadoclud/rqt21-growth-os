from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.enums import Platform


class HeadlineConfigRead(BaseModel):
    id: uuid.UUID
    public_id: str
    brand_id: uuid.UUID
    publishing_connection_id: uuid.UUID | None
    platform: str
    enabled: bool
    interval_hours: int
    max_per_day: int
    topic_rotation_index: int
    last_run_at: datetime | None
    daily_count: int
    daily_count_date: date | None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class HeadlineConfigWrite(BaseModel):
    enabled: bool = False
    publishing_connection_id: uuid.UUID | None = None
    platform: Platform = Platform.FACEBOOK
    interval_hours: int = Field(default=2, ge=1, le=24)
    max_per_day: int = Field(default=12, ge=1, le=24)


class HeadlinePendingPhoto(BaseModel):
    """One of today's already-generated headlines still missing its photo.
    ``scheduled_for`` is the slot time it was assigned when the day's batch
    was generated (see app.workers.headline_scheduler) — the post publishes
    at that time once a photo is uploaded, or immediately if the slot has
    already passed by the time the photo arrives. None only for headlines
    generated before a publishing connection existed, which publish
    immediately on upload instead of waiting for a slot."""

    id: uuid.UUID
    title: str
    caption: str | None
    cta: str | None
    created_at: datetime
    scheduled_for: datetime | None
    model_config = {"from_attributes": True}
