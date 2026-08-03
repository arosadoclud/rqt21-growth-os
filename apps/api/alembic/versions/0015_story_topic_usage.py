"""Add story_topic_usage — one row per generated STORY_AUTO ContentItem,
tracking which topic/category/answer-pair/main-ingredients were used so
app.workers.story_scheduler can enforce a real 7-day cooldown and
same-day category variety across the expanded 45-topic bank.

Revision ID: 0015_story_topic_usage
Revises: 0014_story_schedule
Create Date: 2026-08-03

"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0015_story_topic_usage"
down_revision = "0014_story_schedule"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "story_topic_usage",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("topic_id", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("pair_key", sa.String(length=200), nullable=True),
        sa.Column("ingredients_key", sa.String(length=200), nullable=True),
        sa.Column("normalized_title", sa.String(length=500), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_story_topic_usage"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"],
            name="fk_story_topic_usage_org", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["brand_id"], ["brands.id"],
            name="fk_story_topic_usage_brand", ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_story_topic_usage_organization_id", "story_topic_usage", ["organization_id"]
    )
    op.create_index("ix_story_topic_usage_brand_id", "story_topic_usage", ["brand_id"])
    op.create_index(
        "ix_story_topic_usage_brand_used_at", "story_topic_usage", ["brand_id", "used_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_story_topic_usage_brand_used_at", table_name="story_topic_usage")
    op.drop_index("ix_story_topic_usage_brand_id", table_name="story_topic_usage")
    op.drop_index("ix_story_topic_usage_organization_id", table_name="story_topic_usage")
    op.drop_table("story_topic_usage")
