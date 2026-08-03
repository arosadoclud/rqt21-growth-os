from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid_pk


class StoryTopicUsage(Base):
    """One row per generated STORY_AUTO ContentItem — tracks which topic
    (by app.ai.story_topics.STORY_TOPICS ``id``), category, answer-pair,
    and main ingredients were used, so app.workers.story_scheduler can
    enforce a real 7-day cooldown (never the same topic/pair/ingredient
    combo twice within a week) and same-day category variety (cycle
    through every category before any repeats) — independent of
    whatever freeform title Claude actually generated, since that varies
    even for the same topic."""

    __tablename__ = "story_topic_usage"

    id: Mapped[uuid.UUID] = uuid_pk()
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    topic_id: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    pair_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ingredients_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    normalized_title: Mapped[str] = mapped_column(String(500), nullable=False)
    used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
