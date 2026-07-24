from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk
from app.models.enums import CampaignObjective, CampaignStatus, Platform


class Campaign(Base, TimestampMixin):
    __tablename__ = "campaigns"
    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_campaigns_org_slug"),
        UniqueConstraint("organization_id", "public_id", name="uq_campaigns_org_public_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
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
    public_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    objective: Mapped[CampaignObjective] = mapped_column(
        Enum(CampaignObjective, name="campaign_objective", native_enum=False, length=32),
        nullable=False,
        default=CampaignObjective.OTHER,
    )
    platform: Mapped[Platform] = mapped_column(
        Enum(Platform, name="platform", native_enum=False, length=32),
        nullable=False,
        default=Platform.OTHER,
    )
    status: Mapped[CampaignStatus] = mapped_column(
        Enum(CampaignStatus, name="campaign_status", native_enum=False, length=32),
        nullable=False,
        default=CampaignStatus.DRAFT,
    )
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    budget: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
