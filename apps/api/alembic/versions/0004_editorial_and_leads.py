"""editorial + reviews + leads

Revision ID: 0004_editorial_and_leads
Revises: 0003_growth_domains
Create Date: 2026-07-21

"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0004_editorial_and_leads"
down_revision = "0003_growth_domains"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "editorial_calendar_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("assigned_to_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("platform", sa.String(length=32), nullable=False, server_default="OTHER"),
        sa.Column(
            "content_format", sa.String(length=32), nullable=False, server_default="OTHER"
        ),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="UTC"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="IDEA"),
        sa.Column("priority", sa.String(length=16), nullable=False, server_default="MEDIUM"),
        sa.Column("notes", sa.String(length=4000), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("publication_url", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_editorial_calendar_items"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"],
            name="fk_editorial_items_org", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["content_item_id"], ["content_items.id"],
            name="fk_editorial_items_content", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"], ["campaigns.id"],
            name="fk_editorial_items_campaign", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["brand_id"], ["brands.id"],
            name="fk_editorial_items_brand", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"],
            name="fk_editorial_items_product", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["assigned_to_user_id"], ["users.id"],
            name="fk_editorial_items_assigned", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"],
            name="fk_editorial_items_creator", ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "organization_id", "public_id", name="uq_editorial_items_org_public_id"
        ),
        sa.CheckConstraint(
            "status IN ('IDEA','DRAFT','IN_REVIEW','NEEDS_REVISION','APPROVED','SCHEDULED','PUBLISHED','CANCELLED','ARCHIVED')",
            name="ck_editorial_items_status_valid",
        ),
        sa.CheckConstraint(
            "priority IN ('LOW','MEDIUM','HIGH','URGENT')",
            name="ck_editorial_items_priority_valid",
        ),
    )
    op.create_index(
        "ix_editorial_items_org_scheduled",
        "editorial_calendar_items",
        ["organization_id", "scheduled_for"],
    )
    op.create_index(
        "ix_editorial_items_org_status",
        "editorial_calendar_items",
        ["organization_id", "status"],
    )
    op.create_index(
        "ix_editorial_items_org_campaign",
        "editorial_calendar_items",
        ["organization_id", "campaign_id"],
    )
    op.create_index(
        "ix_editorial_items_public_id", "editorial_calendar_items", ["public_id"]
    )

    op.create_table(
        "reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reviewer_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("review_type", sa.String(length=32), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("comment", sa.String(length=4000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_reviews"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"],
            name="fk_reviews_org", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["content_item_id"], ["content_items.id"],
            name="fk_reviews_content", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_user_id"], ["users.id"],
            name="fk_reviews_reviewer", ondelete="SET NULL",
        ),
        sa.UniqueConstraint("organization_id", "public_id", name="uq_reviews_org_public_id"),
        sa.CheckConstraint(
            "score IS NULL OR (score >= 0 AND score <= 100)",
            name="ck_reviews_score_range",
        ),
        sa.CheckConstraint(
            "decision IN ('APPROVED','NEEDS_REVISION','REJECTED')",
            name="ck_reviews_decision_valid",
        ),
        sa.CheckConstraint(
            "review_type IN ('BRAND','COPY','SEO','CTA','VISUAL','COMPLIANCE','GENERAL')",
            name="ck_reviews_type_valid",
        ),
    )
    op.create_index("ix_reviews_org_content", "reviews", ["organization_id", "content_item_id"])
    op.create_index("ix_reviews_public_id", "reviews", ["public_id"])

    op.create_table(
        "leads",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("content_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tracking_link_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("first_name", sa.String(length=120), nullable=False),
        sa.Column("last_name", sa.String(length=120), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("whatsapp", sa.String(length=40), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="MANUAL"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="NEW"),
        sa.Column("country", sa.String(length=4), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("notes", sa.String(length=4000), nullable=True),
        sa.Column("utm_source", sa.String(length=150), nullable=True),
        sa.Column("utm_medium", sa.String(length=150), nullable=True),
        sa.Column("utm_campaign", sa.String(length=150), nullable=True),
        sa.Column("utm_content", sa.String(length=150), nullable=True),
        sa.Column("utm_term", sa.String(length=150), nullable=True),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("source_system", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_leads"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"],
            name="fk_leads_org", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["brand_id"], ["brands.id"], name="fk_leads_brand", ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], name="fk_leads_product", ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"], ["campaigns.id"], name="fk_leads_campaign", ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["content_item_id"], ["content_items.id"],
            name="fk_leads_content", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tracking_link_id"], ["tracking_links.id"],
            name="fk_leads_tracking_link", ondelete="SET NULL",
        ),
        sa.UniqueConstraint("organization_id", "public_id", name="uq_leads_org_public_id"),
        sa.UniqueConstraint(
            "organization_id", "source_system", "external_id",
            name="uq_leads_org_source_ext",
        ),
        sa.CheckConstraint(
            "status IN ('NEW','CONTACTED','QUALIFIED','PROPOSAL','WON','LOST','ARCHIVED')",
            name="ck_leads_status_valid",
        ),
        sa.CheckConstraint(
            "(email IS NOT NULL AND length(email) > 0) OR "
            "(phone IS NOT NULL AND length(phone) > 0) OR "
            "(whatsapp IS NOT NULL AND length(whatsapp) > 0)",
            name="ck_leads_has_contact",
        ),
    )
    op.create_index("ix_leads_org_status", "leads", ["organization_id", "status"])
    op.create_index("ix_leads_org_created_at", "leads", ["organization_id", "created_at"])
    op.create_index("ix_leads_org_email", "leads", ["organization_id", "email"])
    op.create_index("ix_leads_org_phone", "leads", ["organization_id", "phone"])
    op.create_index("ix_leads_org_campaign", "leads", ["organization_id", "campaign_id"])
    op.create_index(
        "ix_leads_org_tracking_link", "leads", ["organization_id", "tracking_link_id"]
    )
    op.create_index("ix_leads_public_id", "leads", ["public_id"])
    op.create_index("ix_leads_external_id", "leads", ["external_id"])

    op.create_table(
        "lead_activities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("activity_type", sa.String(length=32), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_lead_activities"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"],
            name="fk_lead_activities_org", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["lead_id"], ["leads.id"], name="fk_lead_activities_lead", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["users.id"],
            name="fk_lead_activities_actor", ondelete="SET NULL",
        ),
    )
    op.create_index(
        "ix_lead_activities_org_lead_created",
        "lead_activities",
        ["organization_id", "lead_id", "created_at"],
    )
    op.create_index("ix_lead_activities_public_id", "lead_activities", ["public_id"])


def downgrade() -> None:
    op.drop_index("ix_lead_activities_public_id", table_name="lead_activities")
    op.drop_index("ix_lead_activities_org_lead_created", table_name="lead_activities")
    op.drop_table("lead_activities")

    for idx in (
        "ix_leads_external_id",
        "ix_leads_public_id",
        "ix_leads_org_tracking_link",
        "ix_leads_org_campaign",
        "ix_leads_org_phone",
        "ix_leads_org_email",
        "ix_leads_org_created_at",
        "ix_leads_org_status",
    ):
        op.drop_index(idx, table_name="leads")
    op.drop_table("leads")

    op.drop_index("ix_reviews_public_id", table_name="reviews")
    op.drop_index("ix_reviews_org_content", table_name="reviews")
    op.drop_table("reviews")

    for idx in (
        "ix_editorial_items_public_id",
        "ix_editorial_items_org_campaign",
        "ix_editorial_items_org_status",
        "ix_editorial_items_org_scheduled",
    ):
        op.drop_index(idx, table_name="editorial_calendar_items")
    op.drop_table("editorial_calendar_items")
