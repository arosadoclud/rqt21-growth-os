"""Assets, publishing connections, publications, automations, notifications;
fix prompt_templates uniqueness to partial indexes (NULL-org gap)

Revision ID: 0006_assets_publishing_and_automations
Revises: 0005_ai_generation_and_hardening
Create Date: 2026-07-24

"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0006_assets_publishing_auto"
down_revision = "0005_ai_generation_and_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- P0 fix: prompt_templates uniqueness ------------------------------
    # The old UniqueConstraint(organization_id, name, generation_type, version)
    # never prevented duplicate SYSTEM templates because Postgres treats NULL
    # organization_id as always-distinct in a unique constraint. Replace with
    # two partial unique indexes: one keyed by (generation_type, version) for
    # system templates (organization_id IS NULL), one keyed by
    # (organization_id, generation_type, version) for org templates.
    op.drop_constraint(
        "uq_prompt_template_version", "prompt_templates", type_="unique"
    )
    op.create_index(
        "uq_prompt_templates_system_version",
        "prompt_templates",
        ["generation_type", "version"],
        unique=True,
        postgresql_where=sa.text("organization_id IS NULL"),
    )
    op.create_index(
        "uq_prompt_templates_org_version",
        "prompt_templates",
        ["organization_id", "generation_type", "version"],
        unique=True,
        postgresql_where=sa.text("organization_id IS NOT NULL"),
    )

    # --- assets -------------------------------------------------------
    op.create_table(
        "assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("content_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("uploaded_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("asset_type", sa.String(length=16), nullable=False),
        sa.Column(
            "status", sa.String(length=16), nullable=False, server_default="UPLOADING"
        ),
        sa.Column("storage_provider", sa.String(length=16), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("safe_filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=150), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("alt_text", sa.String(length=500), nullable=True),
        sa.Column("caption", sa.String(length=1000), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_assets"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"],
            name="fk_assets_org", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["brand_id"], ["brands.id"], name="fk_assets_brand", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], name="fk_assets_product", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["content_item_id"], ["content_items.id"],
            name="fk_assets_content_item", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_user_id"], ["users.id"],
            name="fk_assets_uploaded_by", ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "organization_id", "public_id", name="uq_assets_org_public_id"
        ),
        sa.CheckConstraint(
            "asset_type IN ('IMAGE','VIDEO','DOCUMENT','AUDIO','THUMBNAIL','OTHER')",
            name="ck_assets_asset_type_valid",
        ),
        sa.CheckConstraint(
            "status IN ('UPLOADING','PROCESSING','READY','REJECTED','FAILED','ARCHIVED')",
            name="ck_assets_status_valid",
        ),
        sa.CheckConstraint(
            "storage_provider IN ('LOCAL','S3','R2','MOCK')",
            name="ck_assets_storage_provider_valid",
        ),
    )
    op.create_index("ix_assets_organization_id", "assets", ["organization_id"])
    op.create_index("ix_assets_brand_id", "assets", ["brand_id"])
    op.create_index("ix_assets_content_item_id", "assets", ["content_item_id"])
    op.create_index("ix_assets_status", "assets", ["status"])
    op.create_index("ix_assets_checksum_sha256", "assets", ["checksum_sha256"])
    op.create_index("ix_assets_public_id", "assets", ["public_id"])
    op.create_index(
        "ix_assets_org_checksum", "assets", ["organization_id", "checksum_sha256"]
    )

    # --- asset_variants -------------------------------------------------
    op.create_table(
        "asset_variants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("variant_type", sa.String(length=16), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("mime_type", sa.String(length=150), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column(
            "status", sa.String(length=16), nullable=False, server_default="READY"
        ),
        sa.Column(
            "transformation_spec",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_asset_variants"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"],
            name="fk_asset_variants_org", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["asset_id"], ["assets.id"], name="fk_asset_variants_asset", ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "organization_id", "public_id", name="uq_asset_variants_org_public_id"
        ),
        sa.CheckConstraint(
            "variant_type IN ('ORIGINAL','FEED','PORTRAIT','STORY','REEL','THUMBNAIL',"
            "'SQUARE','LANDSCAPE','CUSTOM')",
            name="ck_asset_variants_variant_type_valid",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING','READY','FAILED')",
            name="ck_asset_variants_status_valid",
        ),
    )
    op.create_index("ix_asset_variants_organization_id", "asset_variants", ["organization_id"])
    op.create_index("ix_asset_variants_asset_id", "asset_variants", ["asset_id"])
    op.create_index("ix_asset_variants_public_id", "asset_variants", ["public_id"])

    # --- publishing_connections -------------------------------------------
    op.create_table(
        "publishing_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=16), nullable=False),
        sa.Column("account_name", sa.String(length=255), nullable=False),
        sa.Column("external_account_id", sa.String(length=255), nullable=True),
        sa.Column(
            "status", sa.String(length=16), nullable=False, server_default="PENDING"
        ),
        sa.Column(
            "capabilities",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("credentials_encrypted", sa.String(length=4000), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_publishing_connections"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"],
            name="fk_publishing_connections_org", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["brand_id"], ["brands.id"],
            name="fk_publishing_connections_brand", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"],
            name="fk_publishing_connections_created_by", ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "organization_id", "public_id",
            name="uq_publishing_connections_org_public_id",
        ),
        sa.CheckConstraint(
            "provider IN ('MOCK','MANUAL','META','LINKEDIN','YOUTUBE','TIKTOK','PINTEREST')",
            name="ck_publishing_connections_provider_valid",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING','ACTIVE','EXPIRED','REVOKED','ERROR','DISABLED')",
            name="ck_publishing_connections_status_valid",
        ),
    )
    op.create_index(
        "ix_publishing_connections_organization_id", "publishing_connections", ["organization_id"]
    )
    op.create_index(
        "ix_publishing_connections_brand_id", "publishing_connections", ["brand_id"]
    )
    op.create_index(
        "ix_publishing_connections_status", "publishing_connections", ["status"]
    )
    op.create_index(
        "ix_publishing_connections_public_id", "publishing_connections", ["public_id"]
    )

    # --- publications -------------------------------------------
    op.create_table(
        "publications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("editorial_calendar_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("publishing_connection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("asset_variant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("publication_type", sa.String(length=16), nullable=False),
        sa.Column(
            "status", sa.String(length=16), nullable=False, server_default="DRAFT"
        ),
        sa.Column("caption", sa.String(length=8000), nullable=False, server_default=""),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("cta", sa.String(length=500), nullable=True),
        sa.Column(
            "hashtags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="UTC"),
        sa.Column("external_publication_id", sa.String(length=255), nullable=True),
        sa.Column("external_url", sa.String(length=1000), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("failure_message", sa.String(length=500), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_publications"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"],
            name="fk_publications_org", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["content_item_id"], ["content_items.id"],
            name="fk_publications_content_item", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["editorial_calendar_item_id"], ["editorial_calendar_items.id"],
            name="fk_publications_calendar_item", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["brand_id"], ["brands.id"], name="fk_publications_brand", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"], ["campaigns.id"],
            name="fk_publications_campaign", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"],
            name="fk_publications_product", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["publishing_connection_id"], ["publishing_connections.id"],
            name="fk_publications_connection", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["asset_id"], ["assets.id"], name="fk_publications_asset", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["asset_variant_id"], ["asset_variants.id"],
            name="fk_publications_asset_variant", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"],
            name="fk_publications_created_by", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["approved_by_user_id"], ["users.id"],
            name="fk_publications_approved_by", ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "organization_id", "public_id", name="uq_publications_org_public_id"
        ),
        sa.UniqueConstraint(
            "organization_id", "idempotency_key",
            name="uq_publications_org_idempotency",
        ),
        sa.CheckConstraint(
            "publication_type IN ('POST','REEL','STORY','CAROUSEL','VIDEO','ARTICLE',"
            "'EMAIL','OTHER')",
            name="ck_publications_publication_type_valid",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','READY','SCHEDULED','PUBLISHING','PUBLISHED','FAILED',"
            "'RETRY_SCHEDULED','CANCELLED','ARCHIVED')",
            name="ck_publications_status_valid",
        ),
    )
    op.create_index("ix_publications_organization_id", "publications", ["organization_id"])
    op.create_index("ix_publications_content_item_id", "publications", ["content_item_id"])
    op.create_index(
        "ix_publications_editorial_calendar_item_id", "publications", ["editorial_calendar_item_id"]
    )
    op.create_index("ix_publications_brand_id", "publications", ["brand_id"])
    op.create_index(
        "ix_publications_publishing_connection_id", "publications", ["publishing_connection_id"]
    )
    op.create_index("ix_publications_platform", "publications", ["platform"])
    op.create_index("ix_publications_status", "publications", ["status"])
    op.create_index("ix_publications_scheduled_for", "publications", ["scheduled_for"])
    op.create_index("ix_publications_next_retry_at", "publications", ["next_retry_at"])
    op.create_index("ix_publications_public_id", "publications", ["public_id"])
    op.create_index(
        "ix_publications_org_status", "publications", ["organization_id", "status"]
    )

    # --- publication_attempts -------------------------------------------
    op.create_table(
        "publication_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("publication_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "request_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "response_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_publication_attempts"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"],
            name="fk_publication_attempts_org", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["publication_id"], ["publications.id"],
            name="fk_publication_attempts_publication", ondelete="CASCADE",
        ),
        sa.UniqueConstraint("public_id", name="uq_publication_attempts_public_id"),
        sa.UniqueConstraint(
            "publication_id", "attempt_number",
            name="uq_publication_attempts_pub_number",
        ),
        sa.CheckConstraint(
            "provider IN ('MOCK','MANUAL','META','LINKEDIN','YOUTUBE','TIKTOK','PINTEREST')",
            name="ck_publication_attempts_provider_valid",
        ),
        sa.CheckConstraint(
            "status IN ('STARTED','SUCCEEDED','FAILED','RATE_LIMITED','CANCELLED')",
            name="ck_publication_attempts_status_valid",
        ),
    )
    op.create_index(
        "ix_publication_attempts_organization_id", "publication_attempts", ["organization_id"]
    )
    op.create_index(
        "ix_publication_attempts_publication_id", "publication_attempts", ["publication_id"]
    )
    op.create_index(
        "ix_publication_attempts_public_id", "publication_attempts", ["public_id"]
    )

    # --- automation_rules -------------------------------------------
    op.create_table(
        "automation_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("trigger_type", sa.String(length=32), nullable=False),
        sa.Column(
            "conditions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("action_type", sa.String(length=32), nullable=False),
        sa.Column(
            "action_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("execution_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_automation_rules"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"],
            name="fk_automation_rules_org", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["brand_id"], ["brands.id"], name="fk_automation_rules_brand", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"],
            name="fk_automation_rules_created_by", ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "organization_id", "public_id", name="uq_automation_rules_org_public_id"
        ),
        sa.CheckConstraint(
            "trigger_type IN ('CONTENT_APPROVED','CALENDAR_ITEM_DUE','PUBLICATION_FAILED',"
            "'LEAD_CREATED','LEAD_STATUS_CHANGED')",
            name="ck_automation_rules_trigger_type_valid",
        ),
        sa.CheckConstraint(
            "action_type IN ('CREATE_PUBLICATION_DRAFT','GENERATE_TRACKING_LINK',"
            "'SCHEDULE_RETRY','CREATE_LEAD_ACTIVITY','SEND_INTERNAL_NOTIFICATION')",
            name="ck_automation_rules_action_type_valid",
        ),
    )
    op.create_index("ix_automation_rules_organization_id", "automation_rules", ["organization_id"])
    op.create_index("ix_automation_rules_trigger_type", "automation_rules", ["trigger_type"])
    op.create_index("ix_automation_rules_public_id", "automation_rules", ["public_id"])

    # --- notifications -------------------------------------------
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("notification_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.String(length=1000), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=True),
        sa.Column("resource_public_id", sa.String(length=32), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_notifications"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"],
            name="fk_notifications_org", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_notifications_user", ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "organization_id", "public_id", name="uq_notifications_org_public_id"
        ),
        sa.CheckConstraint(
            "notification_type IN ('CONTENT_APPROVED','PUBLICATION_UPCOMING',"
            "'PUBLICATION_SUCCEEDED','PUBLICATION_FAILED','ASSET_REJECTED',"
            "'CONNECTION_EXPIRED','AI_BUDGET_NEAR_LIMIT','LEAD_WON')",
            name="ck_notifications_notification_type_valid",
        ),
    )
    op.create_index("ix_notifications_organization_id", "notifications", ["organization_id"])
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_public_id", "notifications", ["public_id"])
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_notifications_created_at", table_name="notifications")
    op.drop_index("ix_notifications_public_id", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_index("ix_notifications_organization_id", table_name="notifications")
    op.drop_table("notifications")

    op.drop_index("ix_automation_rules_public_id", table_name="automation_rules")
    op.drop_index("ix_automation_rules_trigger_type", table_name="automation_rules")
    op.drop_index("ix_automation_rules_organization_id", table_name="automation_rules")
    op.drop_table("automation_rules")

    op.drop_index("ix_publication_attempts_public_id", table_name="publication_attempts")
    op.drop_index("ix_publication_attempts_publication_id", table_name="publication_attempts")
    op.drop_index("ix_publication_attempts_organization_id", table_name="publication_attempts")
    op.drop_table("publication_attempts")

    op.drop_index("ix_publications_org_status", table_name="publications")
    op.drop_index("ix_publications_public_id", table_name="publications")
    op.drop_index("ix_publications_next_retry_at", table_name="publications")
    op.drop_index("ix_publications_scheduled_for", table_name="publications")
    op.drop_index("ix_publications_status", table_name="publications")
    op.drop_index("ix_publications_platform", table_name="publications")
    op.drop_index("ix_publications_publishing_connection_id", table_name="publications")
    op.drop_index("ix_publications_brand_id", table_name="publications")
    op.drop_index("ix_publications_editorial_calendar_item_id", table_name="publications")
    op.drop_index("ix_publications_content_item_id", table_name="publications")
    op.drop_index("ix_publications_organization_id", table_name="publications")
    op.drop_table("publications")

    op.drop_index(
        "ix_publishing_connections_public_id", table_name="publishing_connections"
    )
    op.drop_index(
        "ix_publishing_connections_status", table_name="publishing_connections"
    )
    op.drop_index(
        "ix_publishing_connections_brand_id", table_name="publishing_connections"
    )
    op.drop_index(
        "ix_publishing_connections_organization_id", table_name="publishing_connections"
    )
    op.drop_table("publishing_connections")

    op.drop_index("ix_asset_variants_public_id", table_name="asset_variants")
    op.drop_index("ix_asset_variants_asset_id", table_name="asset_variants")
    op.drop_index("ix_asset_variants_organization_id", table_name="asset_variants")
    op.drop_table("asset_variants")

    op.drop_index("ix_assets_org_checksum", table_name="assets")
    op.drop_index("ix_assets_public_id", table_name="assets")
    op.drop_index("ix_assets_checksum_sha256", table_name="assets")
    op.drop_index("ix_assets_status", table_name="assets")
    op.drop_index("ix_assets_content_item_id", table_name="assets")
    op.drop_index("ix_assets_brand_id", table_name="assets")
    op.drop_index("ix_assets_organization_id", table_name="assets")
    op.drop_table("assets")

    op.drop_index("uq_prompt_templates_org_version", table_name="prompt_templates")
    op.drop_index("uq_prompt_templates_system_version", table_name="prompt_templates")
    op.create_unique_constraint(
        "uq_prompt_template_version",
        "prompt_templates",
        ["organization_id", "name", "generation_type", "version"],
    )
