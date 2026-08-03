from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk


class HeadlineSchedule(Base, TimestampMixin):
    """One row per (organization, brand): the config + running state for
    the automatic "Headline" content cycle — app.workers.headline_scheduler
    generates and (if auto-approved) publishes a keto-recipe post every
    interval_hours, up to max_per_day times. A single daily batch fans out
    to BOTH Facebook and Instagram at once — one connection field per
    platform (facebook_connection_id / instagram_connection_id), either
    or both may be set. One photo upload publishes to every platform
    that has a connection configured, simultaneously.

    Created lazily (disabled by default) the first time a user opens the
    Headline screen for a brand — see app.api.v1.headline. Never active
    until a human explicitly flips enabled=True with at least one real
    connection chosen, same "opt-in, never activate on its own" pattern
    as every other real-provider integration in this codebase."""

    __tablename__ = "headline_schedules"
    __table_args__ = (
        UniqueConstraint("organization_id", "brand_id", name="uq_headline_schedules_org_brand"),
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
    interval_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    max_per_day: Mapped[int] = mapped_column(Integer, nullable=False, default=12)
    # Index into app.ai.headline_topics.HEADLINE_TOPICS — advances by one
    # each run so consecutive posts don't repeat the same angle/topic.
    topic_rotation_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Reset to 0 whenever daily_count_date != today — see
    # app.workers.headline_scheduler._due_schedules.
    daily_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    daily_count_date: Mapped[date | None] = mapped_column(Date, nullable=True)
