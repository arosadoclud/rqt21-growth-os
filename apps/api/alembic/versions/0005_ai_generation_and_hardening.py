"""AI generation domain, public lead sources, org regional config

Revision ID: 0005_ai_generation_and_hardening
Revises: 0004_editorial_and_leads
Create Date: 2026-07-23

"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0005_ai_generation_and_hardening"
down_revision = "0004_editorial_and_leads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Organization regional config -------------------------------------
    op.add_column(
        "organizations",
        sa.Column(
            "country_code", sa.String(length=2), nullable=False, server_default="DO"
        ),
    )
    op.add_column(
        "organizations",
        sa.Column(
            "timezone",
            sa.String(length=64),
            nullable=False,
            server_default="America/Santo_Domingo",
        ),
    )
    op.add_column(
        "organizations",
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
    )

    # --- public_lead_sources -------------------------------------------
    op.create_table(
        "public_lead_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("public_token", sa.String(length=128), nullable=False),
        sa.Column(
            "allowed_origins",
            postgresql.ARRAY(sa.String(length=500)),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("default_utm_source", sa.String(length=150), nullable=True),
        sa.Column("default_utm_medium", sa.String(length=150), nullable=True),
        sa.Column("default_utm_campaign", sa.String(length=150), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_public_lead_sources"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"],
            name="fk_public_lead_sources_org", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["brand_id"], ["brands.id"],
            name="fk_public_lead_sources_brand", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"],
            name="fk_public_lead_sources_product", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"], ["campaigns.id"],
            name="fk_public_lead_sources_campaign", ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "organization_id", "public_id", name="uq_public_lead_sources_org_public_id"
        ),
        sa.UniqueConstraint("public_token", name="uq_public_lead_sources_token"),
    )
    op.create_index(
        "ix_public_lead_sources_organization_id", "public_lead_sources", ["organization_id"]
    )
    op.create_index(
        "ix_public_lead_sources_public_id", "public_lead_sources", ["public_id"]
    )
    op.create_index(
        "ix_public_lead_sources_public_token", "public_lead_sources", ["public_token"]
    )

    # --- brand_voice_profiles -------------------------------------------
    op.create_table(
        "brand_voice_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("audience", sa.String(length=2000), nullable=False, server_default=""),
        sa.Column(
            "value_proposition", sa.String(length=2000), nullable=False, server_default=""
        ),
        sa.Column("tone", sa.String(length=1000), nullable=False, server_default=""),
        sa.Column(
            "preferred_terms",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "forbidden_terms",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("cta_style", sa.String(length=1000), nullable=False, server_default=""),
        sa.Column(
            "compliance_notes", sa.String(length=3000), nullable=False, server_default=""
        ),
        sa.Column("language", sa.String(length=16), nullable=False, server_default="es"),
        sa.Column("country", sa.String(length=2), nullable=False, server_default="DO"),
        sa.Column(
            "examples",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_brand_voice_profiles"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"],
            name="fk_brand_voice_profiles_org", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["brand_id"], ["brands.id"],
            name="fk_brand_voice_profiles_brand", ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "organization_id", "brand_id", name="uq_brand_voice_org_brand"
        ),
        sa.UniqueConstraint(
            "organization_id", "public_id", name="uq_brand_voice_org_public_id"
        ),
    )
    op.create_index(
        "ix_brand_voice_profiles_organization_id", "brand_voice_profiles", ["organization_id"]
    )
    op.create_index(
        "ix_brand_voice_profiles_brand_id", "brand_voice_profiles", ["brand_id"]
    )
    op.create_index(
        "ix_brand_voice_profiles_public_id", "brand_voice_profiles", ["public_id"]
    )

    # --- prompt_templates -------------------------------------------
    op.create_table(
        "prompt_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("generation_type", sa.String(length=32), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("system_instructions", sa.String(length=6000), nullable=False),
        sa.Column("user_template", sa.String(length=6000), nullable=False),
        sa.Column(
            "output_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_prompt_templates"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"],
            name="fk_prompt_templates_org", ondelete="CASCADE",
        ),
        sa.UniqueConstraint("public_id", name="uq_prompt_templates_public_id"),
        sa.UniqueConstraint(
            "organization_id", "name", "generation_type", "version",
            name="uq_prompt_template_version",
        ),
        sa.CheckConstraint(
            "generation_type IN ('SOCIAL_POST','REEL_SCRIPT','CAROUSEL','EMAIL',"
            "'BLOG_OUTLINE','BLOG_ARTICLE','CTA_VARIATIONS','CONTENT_IDEAS')",
            name="ck_prompt_templates_generation_type_valid",
        ),
    )
    op.create_index(
        "ix_prompt_templates_organization_id", "prompt_templates", ["organization_id"]
    )
    op.create_index(
        "ix_prompt_templates_generation_type", "prompt_templates", ["generation_type"]
    )
    op.create_index("ix_prompt_templates_public_id", "prompt_templates", ["public_id"])

    # --- generation_jobs -------------------------------------------
    op.create_table(
        "generation_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("generation_type", sa.String(length=32), nullable=False),
        sa.Column(
            "status", sa.String(length=32), nullable=False, server_default="QUEUED"
        ),
        sa.Column("provider", sa.String(length=16), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column(
            "input_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "output_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_cost", sa.Numeric(12, 6), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("retry_of_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("content_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_generation_jobs"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"],
            name="fk_generation_jobs_org", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["brand_id"], ["brands.id"],
            name="fk_generation_jobs_brand", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"],
            name="fk_generation_jobs_product", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"], ["campaigns.id"],
            name="fk_generation_jobs_campaign", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"], ["users.id"],
            name="fk_generation_jobs_requested_by", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["retry_of_job_id"], ["generation_jobs.id"],
            name="fk_generation_jobs_retry_of", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["content_item_id"], ["content_items.id"],
            name="fk_generation_jobs_content_item", ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "organization_id", "public_id", name="uq_generation_jobs_org_public_id"
        ),
        sa.UniqueConstraint(
            "organization_id", "idempotency_key", name="uq_generation_jobs_org_idempotency"
        ),
        sa.CheckConstraint(
            "status IN ('QUEUED','RUNNING','COMPLETED','FAILED','CANCELLED')",
            name="ck_generation_jobs_status_valid",
        ),
        sa.CheckConstraint(
            "provider IN ('ANTHROPIC','OPENAI','MOCK')",
            name="ck_generation_jobs_provider_valid",
        ),
    )
    op.create_index(
        "ix_generation_jobs_organization_id", "generation_jobs", ["organization_id"]
    )
    op.create_index("ix_generation_jobs_brand_id", "generation_jobs", ["brand_id"])
    op.create_index("ix_generation_jobs_product_id", "generation_jobs", ["product_id"])
    op.create_index("ix_generation_jobs_campaign_id", "generation_jobs", ["campaign_id"])
    op.create_index(
        "ix_generation_jobs_requested_by_user_id", "generation_jobs", ["requested_by_user_id"]
    )
    op.create_index(
        "ix_generation_jobs_generation_type", "generation_jobs", ["generation_type"]
    )
    op.create_index("ix_generation_jobs_status", "generation_jobs", ["status"])
    op.create_index(
        "ix_generation_jobs_content_item_id", "generation_jobs", ["content_item_id"]
    )
    op.create_index("ix_generation_jobs_public_id", "generation_jobs", ["public_id"])
    op.create_index(
        "ix_generation_jobs_org_status", "generation_jobs", ["organization_id", "status"]
    )
    op.create_index(
        "ix_generation_jobs_org_created_at",
        "generation_jobs",
        ["organization_id", "created_at"],
    )

    # --- council_reviews -------------------------------------------
    op.create_table(
        "council_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("generation_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewer_type", sa.String(length=32), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("summary", sa.String(length=1000), nullable=False),
        sa.Column(
            "issues",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "recommendations",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "blocking_issues",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_council_reviews"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"],
            name="fk_council_reviews_org", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["generation_job_id"], ["generation_jobs.id"],
            name="fk_council_reviews_job", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["content_item_id"], ["content_items.id"],
            name="fk_council_reviews_content_item", ondelete="SET NULL",
        ),
        sa.UniqueConstraint("public_id", name="uq_council_reviews_public_id"),
        sa.CheckConstraint("score >= 0 AND score <= 100", name="ck_council_reviews_score_range"),
        sa.CheckConstraint(
            "decision IN ('APPROVED','NEEDS_REVISION','REJECTED','BLOCKED')",
            name="ck_council_reviews_decision_valid",
        ),
        sa.CheckConstraint(
            "reviewer_type IN ('BRAND','SEO','EMOTIONAL_TONE','CTA','COMPLIANCE','DEVILS_ADVOCATE')",
            name="ck_council_reviews_reviewer_type_valid",
        ),
    )
    op.create_index(
        "ix_council_reviews_organization_id", "council_reviews", ["organization_id"]
    )
    op.create_index(
        "ix_council_reviews_generation_job_id", "council_reviews", ["generation_job_id"]
    )
    op.create_index("ix_council_reviews_public_id", "council_reviews", ["public_id"])


def downgrade() -> None:
    op.drop_index("ix_council_reviews_public_id", table_name="council_reviews")
    op.drop_index("ix_council_reviews_generation_job_id", table_name="council_reviews")
    op.drop_index("ix_council_reviews_organization_id", table_name="council_reviews")
    op.drop_table("council_reviews")

    for idx in (
        "ix_generation_jobs_org_created_at",
        "ix_generation_jobs_org_status",
        "ix_generation_jobs_public_id",
        "ix_generation_jobs_content_item_id",
        "ix_generation_jobs_status",
        "ix_generation_jobs_generation_type",
        "ix_generation_jobs_requested_by_user_id",
        "ix_generation_jobs_campaign_id",
        "ix_generation_jobs_product_id",
        "ix_generation_jobs_brand_id",
        "ix_generation_jobs_organization_id",
    ):
        op.drop_index(idx, table_name="generation_jobs")
    op.drop_table("generation_jobs")

    op.drop_index("ix_prompt_templates_public_id", table_name="prompt_templates")
    op.drop_index("ix_prompt_templates_generation_type", table_name="prompt_templates")
    op.drop_index("ix_prompt_templates_organization_id", table_name="prompt_templates")
    op.drop_table("prompt_templates")

    op.drop_index(
        "ix_brand_voice_profiles_public_id", table_name="brand_voice_profiles"
    )
    op.drop_index("ix_brand_voice_profiles_brand_id", table_name="brand_voice_profiles")
    op.drop_index(
        "ix_brand_voice_profiles_organization_id", table_name="brand_voice_profiles"
    )
    op.drop_table("brand_voice_profiles")

    op.drop_index(
        "ix_public_lead_sources_public_token", table_name="public_lead_sources"
    )
    op.drop_index("ix_public_lead_sources_public_id", table_name="public_lead_sources")
    op.drop_index(
        "ix_public_lead_sources_organization_id", table_name="public_lead_sources"
    )
    op.drop_table("public_lead_sources")

    op.drop_column("organizations", "currency")
    op.drop_column("organizations", "timezone")
    op.drop_column("organizations", "country_code")
