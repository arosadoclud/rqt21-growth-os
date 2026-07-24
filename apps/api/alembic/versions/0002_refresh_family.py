"""refresh token families + reuse detection

Revision ID: 0002_refresh_family
Revises: 0001_initial
Create Date: 2026-07-21

"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0002_refresh_family"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "refresh_tokens",
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "refresh_tokens",
        sa.Column("reuse_detected_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "refresh_tokens",
        sa.Column("revoked_reason", sa.String(length=64), nullable=True),
    )
    # Backfill existing rows so each becomes its own family.
    op.execute(
        "UPDATE refresh_tokens SET family_id = id WHERE family_id IS NULL"
    )
    op.alter_column("refresh_tokens", "family_id", nullable=False)
    op.create_index(
        "ix_refresh_tokens_family_id", "refresh_tokens", ["family_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_refresh_tokens_family_id", table_name="refresh_tokens")
    op.drop_column("refresh_tokens", "revoked_reason")
    op.drop_column("refresh_tokens", "reuse_detected_at")
    op.drop_column("refresh_tokens", "family_id")
