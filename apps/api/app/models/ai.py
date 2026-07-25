from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk
from app.models.enums import (
    AIProvider,
    CouncilDecision,
    CouncilReviewerType,
    GenerationStatus,
    GenerationType,
)


class PublicLeadSource(Base, TimestampMixin):
    __tablename__ = "public_lead_sources"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "public_id", name="uq_public_lead_sources_org_public_id"
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    public_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="SET NULL"), nullable=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    public_token: Mapped[str] = mapped_column(
        String(128), nullable=False, unique=True, index=True
    )
    allowed_origins: Mapped[list[str]] = mapped_column(
        ARRAY(String(500)), nullable=False, default=list
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    default_utm_source: Mapped[str | None] = mapped_column(String(150), nullable=True)
    default_utm_medium: Mapped[str | None] = mapped_column(String(150), nullable=True)
    default_utm_campaign: Mapped[str | None] = mapped_column(String(150), nullable=True)


class BrandVoiceProfile(Base, TimestampMixin):
    __tablename__ = "brand_voice_profiles"
    __table_args__ = (
        UniqueConstraint("organization_id", "brand_id", name="uq_brand_voice_org_brand"),
        UniqueConstraint(
            "organization_id", "public_id", name="uq_brand_voice_org_public_id"
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    public_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    audience: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    value_proposition: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    tone: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    preferred_terms: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    forbidden_terms: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    cta_style: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    compliance_notes: Mapped[str] = mapped_column(String(3000), nullable=False, default="")
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="es")
    country: Mapped[str] = mapped_column(String(2), nullable=False, default="DO")
    examples: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    # Visual identity directives (background, palette, typography, logo
    # placement, photography style) injected into every IMAGE_ASSET prompt
    # for this brand — see app.ai.runner._build_image_prompt. Free text,
    # not structured, since design briefs don't decompose cleanly into
    # fields and the whole point is to hand it to an image model verbatim.
    visual_style: Mapped[str] = mapped_column(String(4000), nullable=False, default="")


class PromptTemplate(Base, TimestampMixin):
    """Versioned prompt templates.

    Uniqueness is enforced with two PARTIAL indexes rather than a single
    UniqueConstraint, because Postgres treats every NULL as distinct for
    uniqueness purposes — a plain UniqueConstraint including a nullable
    organization_id column silently allows unlimited duplicate SYSTEM
    templates (organization_id IS NULL). See Phase 5 spec section 2.1.

    - uq_prompt_templates_system_version: at most one row per
      (generation_type, version) among system templates (organization_id
      IS NULL).
    - uq_prompt_templates_org_version: at most one row per
      (organization_id, generation_type, version) among org-owned templates.
    """

    __tablename__ = "prompt_templates"
    __table_args__ = (
        Index(
            "uq_prompt_templates_system_version",
            "generation_type",
            "version",
            unique=True,
            postgresql_where=text("organization_id IS NULL"),
        ),
        Index(
            "uq_prompt_templates_org_version",
            "organization_id",
            "generation_type",
            "version",
            unique=True,
            postgresql_where=text("organization_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    public_id: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    generation_type: Mapped[GenerationType] = mapped_column(
        Enum(GenerationType, name="generation_type", native_enum=False, length=32),
        nullable=False,
        index=True,
    )
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    system_instructions: Mapped[str] = mapped_column(String(6000), nullable=False)
    user_template: Mapped[str] = mapped_column(String(6000), nullable=False)
    output_schema: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class GenerationJob(Base, TimestampMixin):
    __tablename__ = "generation_jobs"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "public_id", name="uq_generation_jobs_org_public_id"
        ),
        UniqueConstraint(
            "organization_id", "idempotency_key", name="uq_generation_jobs_org_idempotency"
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    public_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    generation_type: Mapped[GenerationType] = mapped_column(
        Enum(GenerationType, name="generation_type", native_enum=False, length=32),
        nullable=False,
        index=True,
    )
    status: Mapped[GenerationStatus] = mapped_column(
        Enum(GenerationStatus, name="generation_status", native_enum=False, length=32),
        nullable=False,
        default=GenerationStatus.QUEUED,
        index=True,
    )
    provider: Mapped[AIProvider] = mapped_column(
        Enum(AIProvider, name="ai_provider", native_enum=False, length=16), nullable=False
    )
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    input_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    output_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    retry_of_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("generation_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    content_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("content_items.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )


class CouncilReview(Base):
    __tablename__ = "council_reviews"

    id: Mapped[uuid.UUID] = uuid_pk()
    public_id: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    generation_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("generation_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_items.id", ondelete="SET NULL"), nullable=True
    )
    reviewer_type: Mapped[CouncilReviewerType] = mapped_column(
        Enum(CouncilReviewerType, name="council_reviewer_type", native_enum=False, length=32),
        nullable=False,
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    decision: Mapped[CouncilDecision] = mapped_column(
        Enum(CouncilDecision, name="council_decision", native_enum=False, length=32),
        nullable=False,
    )
    summary: Mapped[str] = mapped_column(String(1000), nullable=False)
    issues: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    recommendations: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    blocking_issues: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
