from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk
from app.models.enums import LeadActivityType, LeadSource, LeadStatus, SourceSystem


class Lead(Base, TimestampMixin):
    __tablename__ = "leads"
    __table_args__ = (
        UniqueConstraint("organization_id", "public_id", name="uq_leads_org_public_id"),
        UniqueConstraint(
            "organization_id",
            "source_system",
            "external_id",
            name="uq_leads_org_source_ext",
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
        UUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="SET NULL"),
        nullable=True,
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
    content_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("content_items.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    tracking_link_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tracking_links.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    first_name: Mapped[str] = mapped_column(String(120), nullable=False)
    last_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    whatsapp: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    source: Mapped[LeadSource] = mapped_column(
        Enum(LeadSource, name="lead_source", native_enum=False, length=32),
        nullable=False,
        default=LeadSource.MANUAL,
    )
    status: Mapped[LeadStatus] = mapped_column(
        Enum(LeadStatus, name="lead_status", native_enum=False, length=32),
        nullable=False,
        default=LeadStatus.NEW,
        index=True,
    )
    country: Mapped[str | None] = mapped_column(String(4), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(4000), nullable=True)

    utm_source: Mapped[str | None] = mapped_column(String(150), nullable=True)
    utm_medium: Mapped[str | None] = mapped_column(String(150), nullable=True)
    utm_campaign: Mapped[str | None] = mapped_column(String(150), nullable=True)
    utm_content: Mapped[str | None] = mapped_column(String(150), nullable=True)
    utm_term: Mapped[str | None] = mapped_column(String(150), nullable=True)

    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    source_system: Mapped[SourceSystem | None] = mapped_column(
        Enum(SourceSystem, name="source_system", native_enum=False, length=32),
        nullable=True,
    )


class LeadActivity(Base):
    __tablename__ = "lead_activities"

    id: Mapped[uuid.UUID] = uuid_pk()
    public_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    activity_type: Mapped[LeadActivityType] = mapped_column(
        Enum(LeadActivityType, name="lead_activity_type", native_enum=False, length=32),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    activity_metadata: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )
