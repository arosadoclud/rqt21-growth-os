from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk
from app.models.enums import ContentStatus, ContentType, Platform, SourceSystem


class ContentItem(Base, TimestampMixin):
    __tablename__ = "content_items"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "public_id", name="uq_content_items_org_public_id"
        ),
        UniqueConstraint(
            "organization_id",
            "source_system",
            "external_id",
            name="uq_content_items_org_source_ext",
        ),
    )
    # Note: the GenerationJob -> ContentItem relationship is modeled as a
    # single directional FK on GenerationJob.content_item_id (see
    # app.models.ai.GenerationJob). A reverse FK here would form a circular
    # dependency between these two tables (SQLAlchemy cannot topologically
    # sort mutually-dependent FKs), so it's intentionally not duplicated.

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
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    public_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    source_system: Mapped[SourceSystem] = mapped_column(
        Enum(SourceSystem, name="source_system", native_enum=False, length=32),
        nullable=False,
        default=SourceSystem.MANUAL,
    )
    platform: Mapped[Platform] = mapped_column(
        Enum(Platform, name="platform", native_enum=False, length=32),
        nullable=False,
        default=Platform.OTHER,
    )
    content_type: Mapped[ContentType] = mapped_column(
        Enum(ContentType, name="content_type", native_enum=False, length=32),
        nullable=False,
        default=ContentType.POST,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    hook: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    caption: Mapped[str | None] = mapped_column(String(8000), nullable=True)
    cta: Mapped[str | None] = mapped_column(String(500), nullable=True)
    media_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    publication_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[ContentStatus] = mapped_column(
        Enum(ContentStatus, name="content_status", native_enum=False, length=32),
        nullable=False,
        default=ContentStatus.DRAFT,
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
