from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk


class TrackingLink(Base, TimestampMixin):
    __tablename__ = "tracking_links"
    __table_args__ = (
        UniqueConstraint("short_code", name="uq_tracking_links_short_code"),
        UniqueConstraint(
            "organization_id", "public_id", name="uq_tracking_links_org_public_id"
        ),
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
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    content_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("content_items.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    public_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    short_code: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    destination_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    utm_source: Mapped[str | None] = mapped_column(String(150), nullable=True)
    utm_medium: Mapped[str | None] = mapped_column(String(150), nullable=True)
    utm_campaign: Mapped[str | None] = mapped_column(String(150), nullable=True)
    utm_content: Mapped[str | None] = mapped_column(String(150), nullable=True)
    utm_term: Mapped[str | None] = mapped_column(String(150), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
