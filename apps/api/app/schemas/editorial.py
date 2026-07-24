from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl

from app.models.enums import (
    ContentFormat,
    EditorialPlatform,
    EditorialStatus,
    Priority,
    ReviewDecision,
    ReviewType,
)


class EditorialItemCreate(BaseModel):
    content_item_id: uuid.UUID
    brand_id: uuid.UUID
    campaign_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None
    assigned_to_user_id: uuid.UUID | None = None
    platform: EditorialPlatform = EditorialPlatform.OTHER
    content_format: ContentFormat = ContentFormat.OTHER
    scheduled_for: datetime | None = None
    timezone: str = Field(default="UTC", max_length=64)
    status: EditorialStatus = EditorialStatus.IDEA
    priority: Priority = Priority.MEDIUM
    notes: str | None = Field(default=None, max_length=4000)


class EditorialItemUpdate(BaseModel):
    campaign_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None
    assigned_to_user_id: uuid.UUID | None = None
    platform: EditorialPlatform | None = None
    content_format: ContentFormat | None = None
    scheduled_for: datetime | None = None
    timezone: str | None = None
    status: EditorialStatus | None = None
    priority: Priority | None = None
    notes: str | None = None


class EditorialItemRead(BaseModel):
    id: uuid.UUID
    public_id: str
    content_item_id: uuid.UUID
    brand_id: uuid.UUID
    campaign_id: uuid.UUID | None
    product_id: uuid.UUID | None
    assigned_to_user_id: uuid.UUID | None
    created_by_user_id: uuid.UUID | None
    platform: EditorialPlatform
    content_format: ContentFormat
    scheduled_for: datetime | None
    timezone: str
    status: EditorialStatus
    priority: Priority
    notes: str | None
    published_at: datetime | None
    publication_url: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ScheduleRequest(BaseModel):
    scheduled_for: datetime
    timezone: str = "UTC"


class MarkPublishedRequest(BaseModel):
    publication_url: HttpUrl
    published_at: datetime | None = None


class ReviewCreate(BaseModel):
    review_type: ReviewType = ReviewType.GENERAL
    decision: ReviewDecision
    score: int | None = Field(default=None, ge=0, le=100)
    comment: str | None = Field(default=None, max_length=4000)


class ReviewRead(BaseModel):
    id: uuid.UUID
    public_id: str
    content_item_id: uuid.UUID
    reviewer_user_id: uuid.UUID | None
    review_type: ReviewType
    decision: ReviewDecision
    score: int | None
    comment: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReviewActionRequest(BaseModel):
    comment: str | None = Field(default=None, max_length=4000)
    score: int | None = Field(default=None, ge=0, le=100)
    review_type: ReviewType = ReviewType.GENERAL
