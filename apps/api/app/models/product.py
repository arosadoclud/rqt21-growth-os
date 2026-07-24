from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk
from app.models.enums import ProductStatus


class Product(Base, TimestampMixin):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_products_org_slug"),
        UniqueConstraint("organization_id", "public_id", name="uq_products_org_public_id"),
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
    public_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    checkout_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[ProductStatus] = mapped_column(
        Enum(ProductStatus, name="product_status", native_enum=False, length=32),
        nullable=False,
        default=ProductStatus.DRAFT,
    )
