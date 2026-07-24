from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk
from app.models.enums import AssetStatus, AssetType, StorageProviderName, VariantStatus, VariantType


class Asset(Base, TimestampMixin):
    __tablename__ = "assets"
    __table_args__ = (
        UniqueConstraint("organization_id", "public_id", name="uq_assets_org_public_id"),
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
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="SET NULL"), nullable=True, index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    content_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("content_items.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    uploaded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    asset_type: Mapped[AssetType] = mapped_column(
        Enum(AssetType, name="asset_type", native_enum=False, length=16), nullable=False
    )
    status: Mapped[AssetStatus] = mapped_column(
        Enum(AssetStatus, name="asset_status", native_enum=False, length=16),
        nullable=False,
        default=AssetStatus.UPLOADING,
        index=True,
    )
    storage_provider: Mapped[StorageProviderName] = mapped_column(
        Enum(StorageProviderName, name="storage_provider", native_enum=False, length=16),
        nullable=False,
    )
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    safe_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(150), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    alt_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    caption: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    asset_metadata: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AssetVariant(Base, TimestampMixin):
    __tablename__ = "asset_variants"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "public_id", name="uq_asset_variants_org_public_id"
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
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    variant_type: Mapped[VariantType] = mapped_column(
        Enum(VariantType, name="variant_type", native_enum=False, length=16), nullable=False
    )
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(150), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[VariantStatus] = mapped_column(
        Enum(VariantStatus, name="variant_status", native_enum=False, length=16),
        nullable=False,
        default=VariantStatus.READY,
    )
    transformation_spec: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
