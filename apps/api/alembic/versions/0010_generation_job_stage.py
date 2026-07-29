"""Add stage to generation_jobs — a short human-readable label ("Escribiendo
guion…", "Generando escenas…") updated in-place by the runner as a
long-running VIDEO_ASSET job progresses, so the frontend can show real
pipeline progress instead of a generic spinner while status stays QUEUED
then RUNNING for 1-2 minutes.

Revision ID: 0010_generation_job_stage
Revises: 0009_video_generation
Create Date: 2026-07-28

"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0010_generation_job_stage"
down_revision = "0009_video_generation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "generation_jobs",
        sa.Column("stage", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("generation_jobs", "stage")
