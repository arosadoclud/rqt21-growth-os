"""Add review_status to content_items — a real editorial-review state
machine (NOT_SUBMITTED -> IN_REVIEW -> APPROVED/CHANGES_REQUESTED/REJECTED)
so "Enviar a revisión" can be blocked once a submission is already pending.
Before this, ContentItem had no field tracking review state at all (only
individual Review rows), so nothing stopped a user from submitting the same
content for review any number of times in a row.

Revision ID: 0012_content_review_status
Revises: 0011_voice_over_generation
Create Date: 2026-07-29

"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0012_content_review_status"
down_revision = "0011_voice_over_generation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "content_items",
        sa.Column(
            "review_status",
            sa.String(length=32),
            nullable=False,
            server_default="NOT_SUBMITTED",
        ),
    )
    op.create_check_constraint(
        "ck_content_items_review_status_valid",
        "content_items",
        "review_status IN ('NOT_SUBMITTED','IN_REVIEW','APPROVED','CHANGES_REQUESTED','REJECTED')",
    )
    op.alter_column("content_items", "review_status", server_default=None)


def downgrade() -> None:
    op.drop_constraint("ck_content_items_review_status_valid", "content_items", type_="check")
    op.drop_column("content_items", "review_status")
