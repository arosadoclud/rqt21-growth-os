from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import (
    AIProvider,
    CouncilDecision,
    CouncilReviewerType,
    GenerationStatus,
    GenerationType,
)


class PublicLeadSourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    brand_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None
    campaign_id: uuid.UUID | None = None
    allowed_origins: list[str] = Field(default_factory=list, max_length=30)
    expires_at: datetime | None = None
    default_utm_source: str | None = Field(default=None, max_length=150)
    default_utm_medium: str | None = Field(default=None, max_length=150)
    default_utm_campaign: str | None = Field(default=None, max_length=150)


class PublicLeadSourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    allowed_origins: list[str] | None = Field(default=None, max_length=30)
    expires_at: datetime | None = None
    brand_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None
    campaign_id: uuid.UUID | None = None
    default_utm_source: str | None = Field(default=None, max_length=150)
    default_utm_medium: str | None = Field(default=None, max_length=150)
    default_utm_campaign: str | None = Field(default=None, max_length=150)


class PublicLeadSourceRead(PublicLeadSourceCreate):
    id: uuid.UUID
    public_id: str
    public_token: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class BrandVoiceWrite(BaseModel):
    brand_id: uuid.UUID
    audience: str = Field(default="", max_length=2000)
    value_proposition: str = Field(default="", max_length=2000)
    tone: str = Field(default="", max_length=1000)
    preferred_terms: list[str] = Field(default_factory=list, max_length=50)
    forbidden_terms: list[str] = Field(default_factory=list, max_length=50)
    cta_style: str = Field(default="", max_length=1000)
    compliance_notes: str = Field(default="", max_length=3000)
    language: str = Field(default="es", max_length=16)
    country: str = Field(default="DO", min_length=2, max_length=2)
    examples: list[str] = Field(default_factory=list, max_length=20)
    visual_style: str = Field(default="", max_length=4000)


class BrandVoiceRead(BrandVoiceWrite):
    id: uuid.UUID
    public_id: str
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class GenerationInput(BaseModel):
    objective: str = Field(min_length=1, max_length=500)
    platform: str = Field(default="INSTAGRAM", max_length=50)
    topic: str = Field(min_length=1, max_length=1000)
    audience: str | None = Field(default=None, max_length=1000)
    cta: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=2000)


class GenerationJobCreate(BaseModel):
    brand_id: uuid.UUID
    product_id: uuid.UUID | None = None
    campaign_id: uuid.UUID | None = None
    generation_type: GenerationType
    input: GenerationInput
    idempotency_key: str | None = Field(default=None, max_length=128)


class GeneratedContent(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    hook: str | None = Field(default=None, max_length=1000)
    script: str | None = Field(default=None, max_length=8000)
    caption: str | None = Field(default=None, max_length=8000)
    cta: str | None = Field(default=None, max_length=500)
    hashtags: list[str] = Field(default_factory=list, max_length=30)
    visual_notes: list[str] = Field(default_factory=list, max_length=20)
    ideas: list[str] = Field(default_factory=list, max_length=30)
    stock_search_terms: list[str] = Field(default_factory=list, max_length=20)


class GenerationJobRead(BaseModel):
    id: uuid.UUID
    public_id: str
    brand_id: uuid.UUID
    product_id: uuid.UUID | None
    campaign_id: uuid.UUID | None
    requested_by_user_id: uuid.UUID
    generation_type: GenerationType
    status: GenerationStatus
    provider: AIProvider
    model: str
    prompt_version: str
    input_payload: dict[str, Any] | None
    output_payload: dict[str, Any] | None
    error_code: str | None
    error_message: str | None
    stage: str | None
    input_tokens: int | None
    output_tokens: int | None
    estimated_cost: Decimal | None
    started_at: datetime | None
    completed_at: datetime | None
    content_item_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    visibility: str = "full"
    model_config = {"from_attributes": True}


_AI_INTERNALS_ROLES = {"OWNER", "ADMIN", "MARKETER"}


def serialize_job_for_role(job, role) -> GenerationJobRead:
    """OWNER/ADMIN/MARKETER see the full job including the rendered prompt
    and estimated cost. ANALYST/VIEWER get everything else (status, type,
    structured output, token counts) but never the internal prompt or cost —
    see Phase 4 spec section 12 RBAC."""
    role_name = role.value if hasattr(role, "value") else str(role)
    data = GenerationJobRead.model_validate(job).model_dump()
    if role_name not in _AI_INTERNALS_ROLES:
        data["input_payload"] = None
        data["estimated_cost"] = None
        data["visibility"] = "restricted"
    return GenerationJobRead(**data)


class CouncilReviewRead(BaseModel):
    id: uuid.UUID
    public_id: str
    generation_job_id: uuid.UUID
    content_item_id: uuid.UUID | None
    reviewer_type: CouncilReviewerType
    score: int
    decision: CouncilDecision
    summary: str
    issues: list[str]
    recommendations: list[str]
    blocking_issues: list[str]
    created_at: datetime
    model_config = {"from_attributes": True}


class CouncilDecisionResult(BaseModel):
    score: float
    decision: CouncilDecision
    reviews: list[CouncilReviewRead]
    issues: list[str]
    recommendations: list[str]
    blocking_issues: list[str]
    created_at: datetime


class CreateContentFromJob(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    hook: str | None = Field(default=None, max_length=2000)
    caption: str | None = Field(default=None, max_length=8000)
    cta: str | None = Field(default=None, max_length=500)


class AIUsageSummary(BaseModel):
    jobs_total: int
    jobs_completed: int
    jobs_failed: int
    input_tokens: int
    output_tokens: int
    estimated_cost: Decimal
    monthly_budget: Decimal
    by_provider: dict[str, int]
    by_type: dict[str, int]
    by_brand: dict[str, int]
