from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.models.enums import (
    AttemptStatus,
    ConnectionStatus,
    Platform,
    PublicationStatus,
    PublicationType,
    PublishingProviderName,
)

# ---------- Connections ----------


class PublishingConnectionCreate(BaseModel):
    brand_id: uuid.UUID
    platform: Platform
    provider: PublishingProviderName
    account_name: str = Field(min_length=1, max_length=255)
    external_account_id: str | None = Field(default=None, max_length=255)
    capabilities: list[str] = Field(default_factory=list, max_length=20)
    # Only used for MOCK/META in this MVP; MANUAL connections carry none.
    credentials: dict[str, Any] | None = None
    token_expires_at: datetime | None = None


class PublishingConnectionUpdate(BaseModel):
    account_name: str | None = Field(default=None, min_length=1, max_length=255)
    capabilities: list[str] | None = None
    credentials: dict[str, Any] | None = None
    token_expires_at: datetime | None = None


class PublishingConnectionRead(BaseModel):
    id: uuid.UUID
    public_id: str
    brand_id: uuid.UUID
    platform: Platform
    provider: PublishingProviderName
    account_name: str
    external_account_id: str | None
    status: ConnectionStatus
    capabilities: list[str]
    credentials_last_four: str | None = None
    token_expires_at: datetime | None
    last_verified_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------- Publications ----------


# Applies to both AI-generated and manually-entered publications alike —
# the "≤200 words caption+cta, exactly ≤5 hashtags" rule isn't specific to
# the AI prompt, it's a content-quality rule for anything actually published.
_MAX_CAPTION_CTA_WORDS = 200
_MAX_HASHTAGS = 5


def _check_caption_cta_and_hashtags(caption: str | None, cta: str | None, hashtags: list[str] | None) -> None:
    combined = " ".join(p for p in (caption, cta) if p)
    word_count = len(combined.split())
    if word_count > _MAX_CAPTION_CTA_WORDS:
        raise ValueError(
            f"caption + cta combined must not exceed {_MAX_CAPTION_CTA_WORDS} words "
            f"(got {word_count})"
        )
    if hashtags is not None and len(hashtags) > _MAX_HASHTAGS:
        raise ValueError(f"hashtags must not exceed {_MAX_HASHTAGS} items (got {len(hashtags)})")


class PublicationCreate(BaseModel):
    content_item_id: uuid.UUID
    editorial_calendar_item_id: uuid.UUID | None = None
    brand_id: uuid.UUID
    campaign_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None
    publishing_connection_id: uuid.UUID
    asset_id: uuid.UUID | None = None
    asset_variant_id: uuid.UUID | None = None
    platform: Platform
    publication_type: PublicationType
    caption: str = Field(default="", max_length=8000)
    title: str | None = Field(default=None, max_length=500)
    cta: str | None = Field(default=None, max_length=500)
    hashtags: list[str] = Field(default_factory=list, max_length=40)
    idempotency_key: str | None = Field(default=None, max_length=128)

    @model_validator(mode="after")
    def _validate_content_limits(self) -> PublicationCreate:
        _check_caption_cta_and_hashtags(self.caption, self.cta, self.hashtags)
        return self


class PublicationUpdate(BaseModel):
    caption: str | None = Field(default=None, max_length=8000)
    title: str | None = Field(default=None, max_length=500)
    cta: str | None = Field(default=None, max_length=500)
    hashtags: list[str] | None = Field(default=None, max_length=40)
    asset_id: uuid.UUID | None = None
    asset_variant_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _validate_content_limits(self) -> PublicationUpdate:
        # Partial updates only validate the fields present in this request —
        # a full cross-field check against the stored row happens if/when
        # caption+cta+hashtags are all touched together; this still catches
        # the common case (editing caption/cta/hashtags in the same call).
        if self.caption is not None or self.cta is not None or self.hashtags is not None:
            _check_caption_cta_and_hashtags(self.caption, self.cta, self.hashtags)
        return self


class ScheduleRequest(BaseModel):
    scheduled_for: datetime
    timezone: str = Field(default="UTC", max_length=64)


class MarkPublishedRequest(BaseModel):
    external_url: str = Field(min_length=1, max_length=1000)
    published_at: datetime | None = None


class PublicationRead(BaseModel):
    id: uuid.UUID
    public_id: str
    content_item_id: uuid.UUID
    editorial_calendar_item_id: uuid.UUID | None
    brand_id: uuid.UUID
    campaign_id: uuid.UUID | None
    product_id: uuid.UUID | None
    publishing_connection_id: uuid.UUID
    asset_id: uuid.UUID | None
    asset_variant_id: uuid.UUID | None
    platform: Platform
    publication_type: PublicationType
    status: PublicationStatus
    caption: str
    title: str | None
    cta: str | None
    hashtags: list[str]
    scheduled_for: datetime | None
    timezone: str
    external_publication_id: str | None
    external_url: str | None
    published_at: datetime | None
    failure_code: str | None
    failure_message: str | None
    attempt_count: int
    next_retry_at: datetime | None
    idempotency_key: str
    created_by_user_id: uuid.UUID | None
    approved_by_user_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ValidationResultSchema(BaseModel):
    ok: bool
    errors: list[str]
    warnings: list[str]


class PublicationAttemptRead(BaseModel):
    id: uuid.UUID
    public_id: str
    publication_id: uuid.UUID
    attempt_number: int
    provider: PublishingProviderName
    status: AttemptStatus
    request_summary: dict[str, Any]
    response_summary: dict[str, Any]
    external_id: str | None
    error_code: str | None
    error_message: str | None
    started_at: datetime
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PublishingSummary(BaseModel):
    scheduled: int
    published: int
    failed: int
    success_rate: float
    retries: int
    by_platform: dict[str, int]
    upcoming_7_days: int
    connections_with_error: int
