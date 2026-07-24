from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk
from app.models.enums import (
    ContentFormat,
    EditorialPlatform,
    EditorialStatus,
    Priority,
    ReviewDecision,
    ReviewType,
)


class EditorialCalendarItem(Base, TimestampMixin):
    __tablename__ = "editorial_calendar_items"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "public_id", name="uq_editorial_items_org_public_id"
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
    content_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("content_items.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="SET NULL"),
        nullable=True,
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
    assigned_to_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    platform: Mapped[EditorialPlatform] = mapped_column(
        Enum(
            EditorialPlatform,
            name="editorial_platform",
            native_enum=False,
            length=32,
        ),
        nullable=False,
        default=EditorialPlatform.OTHER,
    )
    content_format: Mapped[ContentFormat] = mapped_column(
        Enum(ContentFormat, name="content_format", native_enum=False, length=32),
        nullable=False,
        default=ContentFormat.OTHER,
    )
    scheduled_for: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    status: Mapped[EditorialStatus] = mapped_column(
        Enum(EditorialStatus, name="editorial_status", native_enum=False, length=32),
        nullable=False,
        default=EditorialStatus.IDEA,
        index=True,
    )
    priority: Mapped[Priority] = mapped_column(
        Enum(Priority, name="editorial_priority", native_enum=False, length=16),
        nullable=False,
        default=Priority.MEDIUM,
    )
    notes: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    publication_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)


class Review(Base, TimestampMixin):
    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("organization_id", "public_id", name="uq_reviews_org_public_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    public_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("content_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reviewer_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    review_type: Mapped[ReviewType] = mapped_column(
        Enum(ReviewType, name="review_type", native_enum=False, length=32),
        nullable=False,
    )
    decision: Mapped[ReviewDecision] = mapped_column(
        Enum(ReviewDecision, name="review_decision", native_enum=False, length=32),
        nullable=False,
    )
    score: Mapped[int | None] = mapped_column(nullable=True)
    comment: Mapped[str | None] = mapped_column(String(4000), nullable=True)
