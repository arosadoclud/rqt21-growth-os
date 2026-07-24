from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import AutomationActionType, AutomationTriggerType, NotificationType


class AutomationRuleCreate(BaseModel):
    brand_id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=255)
    trigger_type: AutomationTriggerType
    conditions: dict[str, Any] = Field(default_factory=dict)
    action_type: AutomationActionType
    action_config: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class AutomationRuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    conditions: dict[str, Any] | None = None
    action_config: dict[str, Any] | None = None
    is_active: bool | None = None


class AutomationRuleRead(BaseModel):
    id: uuid.UUID
    public_id: str
    brand_id: uuid.UUID | None
    name: str
    trigger_type: AutomationTriggerType
    conditions: dict[str, Any]
    action_type: AutomationActionType
    action_config: dict[str, Any]
    is_active: bool
    execution_count: int
    last_executed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AutomationSummary(BaseModel):
    active_rules: int
    total_executions: int
    loop_preventions: int


class NotificationRead(BaseModel):
    id: uuid.UUID
    public_id: str
    notification_type: NotificationType
    title: str
    message: str
    resource_type: str | None
    resource_public_id: str | None
    read_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
