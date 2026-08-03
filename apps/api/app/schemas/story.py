from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class StoryConfigRead(BaseModel):
    id: uuid.UUID
    public_id: str
    brand_id: uuid.UUID
    facebook_connection_id: uuid.UUID | None
    instagram_connection_id: uuid.UUID | None
    enabled: bool
    interval_minutes: int
    max_per_day: int
    topic_rotation_index: int
    last_run_at: datetime | None
    daily_count: int
    daily_count_date: date | None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class StoryConfigWrite(BaseModel):
    enabled: bool = False
    facebook_connection_id: uuid.UUID | None = None
    instagram_connection_id: uuid.UUID | None = None
    interval_minutes: int = Field(default=40, ge=10, le=360)
    max_per_day: int = Field(default=12, ge=1, le=36)


class StoryPendingPhoto(BaseModel):
    """One of today's already-generated stories still missing its photo.
    ``scheduled_for`` is the slot time it was assigned when the day's
    batch was generated (see app.workers.story_scheduler) — the story
    publishes at that time once a photo is uploaded, or immediately if
    the slot has already passed by the time the photo arrives. None only
    for stories generated before a publishing connection existed, which
    publish immediately on upload instead of waiting for a slot."""

    id: uuid.UUID
    title: str
    caption: str | None
    cta: str | None
    created_at: datetime
    scheduled_for: datetime | None
    model_config = {"from_attributes": True}
