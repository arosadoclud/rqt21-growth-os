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
