from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk
from app.models.enums import (
    AttemptStatus,
    ConnectionStatus,
    Platform,
    PublicationStatus,
    PublicationType,
    PublishingProviderName,
)


class PublishingConnection(Base, TimestampMixin):
    __tablename__ = "publishing_connections"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "public_id", name="uq_publishing_connections_org_public_id"
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
    platform: Mapped[Platform] = mapped_column(
        Enum(Platform, name="platform", native_enum=False, length=32), nullable=False
    )
    provider: Mapped[PublishingProviderName] = mapped_column(
        Enum(
            PublishingProviderName,
            name="publishing_provider",
            native_enum=False,
            length=16,
        ),
        nullable=False,
    )
    account_name: Mapped[str] = mapped_column(String(255), nullable=False)
    external_account_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[ConnectionStatus] = mapped_column(
        Enum(ConnectionStatus, name="connection_status", native_enum=False, length=16),
        nullable=False,
        default=ConnectionStatus.PENDING,
        index=True,
    )
    capabilities: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    # Fernet-encrypted JSON blob. Never serialized back to any API response —
    # see app.schemas.publishing.PublishingConnectionRead, which omits it.
    credentials_encrypted: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class Publication(Base, TimestampMixin):
    __tablename__ = "publications"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "public_id", name="uq_publications_org_public_id"
        ),
        UniqueConstraint(
            "organization_id", "idempotency_key", name="uq_publications_org_idempotency"
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
    editorial_calendar_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("editorial_calendar_items.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    publishing_connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("publishing_connections.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id", ondelete="SET NULL"), nullable=True
    )
    asset_variant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("asset_variants.id", ondelete="SET NULL"),
        nullable=True,
    )
    platform: Mapped[Platform] = mapped_column(
        Enum(Platform, name="platform", native_enum=False, length=32), nullable=False
    )
    publication_type: Mapped[PublicationType] = mapped_column(
        Enum(PublicationType, name="publication_type", native_enum=False, length=16),
        nullable=False,
    )
    status: Mapped[PublicationStatus] = mapped_column(
        Enum(PublicationStatus, name="publication_status", native_enum=False, length=16),
        nullable=False,
        default=PublicationStatus.DRAFT,
        index=True,
    )
    caption: Mapped[str] = mapped_column(String(8000), nullable=False, default="")
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cta: Mapped[str | None] = mapped_column(String(500), nullable=True)
    hashtags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    scheduled_for: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    external_publication_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class PublicationAttempt(Base):
    __tablename__ = "publication_attempts"
    __table_args__ = (
        UniqueConstraint(
            "publication_id", "attempt_number", name="uq_publication_attempts_pub_number"
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    public_id: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    publication_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("publications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    provider: Mapped[PublishingProviderName] = mapped_column(
        Enum(
            PublishingProviderName,
            name="publishing_provider",
            native_enum=False,
            length=16,
        ),
        nullable=False,
    )
    status: Mapped[AttemptStatus] = mapped_column(
        Enum(AttemptStatus, name="attempt_status", native_enum=False, length=16),
        nullable=False,
    )
    request_summary: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    response_summary: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
