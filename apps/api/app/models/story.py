from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk


class StorySchedule(Base, TimestampMixin):
    """One row per (organization, brand): the config + running state for
    the automatic "Historias" content cycle — app.workers.story_scheduler.
    A single daily batch of topics/photos fans out to BOTH Facebook and
    Instagram at once — one connection field per platform
    (facebook_connection_id / instagram_connection_id), either or both
    may be set. One photo upload publishes to every platform that has a
    connection configured, simultaneously — there is no separate
    "Facebook cycle" vs "Instagram cycle" to run or upload to twice.

    Same "generate the whole day's batch at once, human uploads the
    photo, publish_due fires it at its slot" pattern as HeadlineSchedule
    (see app.models.headline), but deliberately different in kind: short,
    conversational, follower-connection content (questions, polls,
    behind-the-scenes) on a much tighter cadence (interval_minutes,
    default 40) instead of Headline's interval_hours — Stories are
    ephemeral (24h) and consumed differently than a feed post.

    Created lazily (disabled by default) the first time a user opens the
    Historias screen for a brand — see app.api.v1.story. Never active
    until a human explicitly flips enabled=True with at least one real
    connection chosen, same "opt-in, never activate on its own" pattern
    as every other real-provider integration in this codebase."""

    __tablename__ = "story_schedules"
    __table_args__ = (
        UniqueConstraint("organization_id", "brand_id", name="uq_story_schedules_org_brand"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    public_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
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
    facebook_connection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("publishing_connections.id", ondelete="SET NULL"),
        nullable=True,
    )
    instagram_connection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("publishing_connections.id", ondelete="SET NULL"),
        nullable=True,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=40)
    max_per_day: Mapped[int] = mapped_column(Integer, nullable=False, default=12)
    # Index into app.ai.story_topics.STORY_TOPICS — advances by one each
    # run so consecutive stories don't repeat the same angle/topic.
    topic_rotation_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Reset to 0 whenever daily_count_date != today — see
    # app.workers.story_scheduler._due_for_batch.
    daily_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    daily_count_date: Mapped[date | None] = mapped_column(Date, nullable=True)
