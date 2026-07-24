"""growth domains: brands, products, campaigns, content, tracking, clicks

Revision ID: 0003_growth_domains
Revises: 0002_refresh_family
Create Date: 2026-07-21

"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0003_growth_domains"
down_revision = "0002_refresh_family"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "brands",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=True),
        sa.Column("website_url", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_brands"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"],
            name="fk_brands_organization_id_organizations", ondelete="CASCADE",
        ),
        sa.UniqueConstraint("organization_id", "slug", name="uq_brands_org_slug"),
        sa.UniqueConstraint("organization_id", "public_id", name="uq_brands_org_public_id"),
    )
    op.create_index("ix_brands_organization_id", "brands", ["organization_id"])
    op.create_index("ix_brands_public_id", "brands", ["public_id"])

    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("description", sa.String(length=4000), nullable=True),
        sa.Column("price", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
        sa.Column("checkout_url", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="DRAFT"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_products"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"],
            name="fk_products_organization_id_organizations", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["brand_id"], ["brands.id"],
            name="fk_products_brand_id_brands", ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("organization_id", "slug", name="uq_products_org_slug"),
        sa.UniqueConstraint("organization_id", "public_id", name="uq_products_org_public_id"),
        sa.CheckConstraint(
            "status IN ('DRAFT','ACTIVE','ARCHIVED')",
            name="ck_products_status_valid",
        ),
    )
    op.create_index("ix_products_organization_id", "products", ["organization_id"])
    op.create_index("ix_products_brand_id", "products", ["brand_id"])
    op.create_index("ix_products_public_id", "products", ["public_id"])

    op.create_table(
        "campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("objective", sa.String(length=32), nullable=False, server_default="OTHER"),
        sa.Column("platform", sa.String(length=32), nullable=False, server_default="OTHER"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="DRAFT"),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("budget", sa.Numeric(12, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_campaigns"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"],
            name="fk_campaigns_organization_id_organizations", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["brand_id"], ["brands.id"],
            name="fk_campaigns_brand_id_brands", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"],
            name="fk_campaigns_product_id_products", ondelete="SET NULL",
        ),
        sa.UniqueConstraint("organization_id", "slug", name="uq_campaigns_org_slug"),
        sa.UniqueConstraint(
            "organization_id", "public_id", name="uq_campaigns_org_public_id"
        ),
    )
    op.create_index("ix_campaigns_organization_id", "campaigns", ["organization_id"])
    op.create_index("ix_campaigns_brand_id", "campaigns", ["brand_id"])
    op.create_index("ix_campaigns_product_id", "campaigns", ["product_id"])
    op.create_index("ix_campaigns_public_id", "campaigns", ["public_id"])

    op.create_table(
        "content_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column(
            "source_system", sa.String(length=32), nullable=False, server_default="MANUAL"
        ),
        sa.Column("platform", sa.String(length=32), nullable=False, server_default="OTHER"),
        sa.Column("content_type", sa.String(length=32), nullable=False, server_default="POST"),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("hook", sa.String(length=2000), nullable=True),
        sa.Column("caption", sa.String(length=8000), nullable=True),
        sa.Column("cta", sa.String(length=500), nullable=True),
        sa.Column("media_url", sa.String(length=1000), nullable=True),
        sa.Column("publication_url", sa.String(length=1000), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="DRAFT"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_content_items"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"],
            name="fk_content_items_organization_id_organizations", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["brand_id"], ["brands.id"],
            name="fk_content_items_brand_id_brands", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"], ["campaigns.id"],
            name="fk_content_items_campaign_id_campaigns", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"],
            name="fk_content_items_product_id_products", ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "organization_id", "public_id", name="uq_content_items_org_public_id"
        ),
        sa.UniqueConstraint(
            "organization_id", "source_system", "external_id",
            name="uq_content_items_org_source_ext",
        ),
    )
    op.create_index("ix_content_items_organization_id", "content_items", ["organization_id"])
    op.create_index("ix_content_items_brand_id", "content_items", ["brand_id"])
    op.create_index("ix_content_items_campaign_id", "content_items", ["campaign_id"])
    op.create_index("ix_content_items_product_id", "content_items", ["product_id"])
    op.create_index("ix_content_items_public_id", "content_items", ["public_id"])
    op.create_index("ix_content_items_external_id", "content_items", ["external_id"])

    op.create_table(
        "tracking_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("content_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("short_code", sa.String(length=24), nullable=False),
        sa.Column("destination_url", sa.String(length=2000), nullable=False),
        sa.Column("utm_source", sa.String(length=150), nullable=True),
        sa.Column("utm_medium", sa.String(length=150), nullable=True),
        sa.Column("utm_campaign", sa.String(length=150), nullable=True),
        sa.Column("utm_content", sa.String(length=150), nullable=True),
        sa.Column("utm_term", sa.String(length=150), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_tracking_links"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"],
            name="fk_tracking_links_organization_id_organizations", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["brand_id"], ["brands.id"],
            name="fk_tracking_links_brand_id_brands", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"],
            name="fk_tracking_links_product_id_products", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"], ["campaigns.id"],
            name="fk_tracking_links_campaign_id_campaigns", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["content_id"], ["content_items.id"],
            name="fk_tracking_links_content_id_content_items", ondelete="SET NULL",
        ),
        sa.UniqueConstraint("short_code", name="uq_tracking_links_short_code"),
        sa.UniqueConstraint(
            "organization_id", "public_id", name="uq_tracking_links_org_public_id"
        ),
    )
    op.create_index("ix_tracking_links_organization_id", "tracking_links", ["organization_id"])
    op.create_index("ix_tracking_links_brand_id", "tracking_links", ["brand_id"])
    op.create_index("ix_tracking_links_campaign_id", "tracking_links", ["campaign_id"])
    op.create_index("ix_tracking_links_content_id", "tracking_links", ["content_id"])
    op.create_index("ix_tracking_links_short_code", "tracking_links", ["short_code"])
    op.create_index("ix_tracking_links_public_id", "tracking_links", ["public_id"])

    op.create_table(
        "click_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tracking_link_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("referrer", sa.String(length=1000), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        sa.Column("country", sa.String(length=4), nullable=True),
        sa.Column("device_type", sa.String(length=20), nullable=True),
        sa.Column("browser", sa.String(length=30), nullable=True),
        sa.Column("os", sa.String(length=30), nullable=True),
        sa.Column(
            "query_params",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_click_events"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"],
            name="fk_click_events_organization_id_organizations", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tracking_link_id"], ["tracking_links.id"],
            name="fk_click_events_tracking_link_id_tracking_links", ondelete="CASCADE",
        ),
    )
    op.create_index("ix_click_events_organization_id", "click_events", ["organization_id"])
    op.create_index("ix_click_events_tracking_link_id", "click_events", ["tracking_link_id"])
    op.create_index("ix_click_events_occurred_at", "click_events", ["occurred_at"])
    op.create_index("ix_click_events_ip_hash", "click_events", ["ip_hash"])


def downgrade() -> None:
    op.drop_index("ix_click_events_ip_hash", table_name="click_events")
    op.drop_index("ix_click_events_occurred_at", table_name="click_events")
    op.drop_index("ix_click_events_tracking_link_id", table_name="click_events")
    op.drop_index("ix_click_events_organization_id", table_name="click_events")
    op.drop_table("click_events")

    for idx in (
        "ix_tracking_links_public_id",
        "ix_tracking_links_short_code",
        "ix_tracking_links_content_id",
        "ix_tracking_links_campaign_id",
        "ix_tracking_links_brand_id",
        "ix_tracking_links_organization_id",
    ):
        op.drop_index(idx, table_name="tracking_links")
    op.drop_table("tracking_links")

    for idx in (
        "ix_content_items_external_id",
        "ix_content_items_public_id",
        "ix_content_items_product_id",
        "ix_content_items_campaign_id",
        "ix_content_items_brand_id",
        "ix_content_items_organization_id",
    ):
        op.drop_index(idx, table_name="content_items")
    op.drop_table("content_items")

    for idx in (
        "ix_campaigns_public_id",
        "ix_campaigns_product_id",
        "ix_campaigns_brand_id",
        "ix_campaigns_organization_id",
    ):
        op.drop_index(idx, table_name="campaigns")
    op.drop_table("campaigns")

    for idx in (
        "ix_products_public_id",
        "ix_products_brand_id",
        "ix_products_organization_id",
    ):
        op.drop_index(idx, table_name="products")
    op.drop_table("products")

    op.drop_index("ix_brands_public_id", table_name="brands")
    op.drop_index("ix_brands_organization_id", table_name="brands")
    op.drop_table("brands")
