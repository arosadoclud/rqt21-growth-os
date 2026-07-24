from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid_pk


class ClickEvent(Base):
    __tablename__ = "click_events"

    id: Mapped[uuid.UUID] = uuid_pk()
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tracking_link_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tracking_links.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    referrer: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    country: Mapped[str | None] = mapped_column(String(4), nullable=True)
    device_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    browser: Mapped[str | None] = mapped_column(String(30), nullable=True)
    os: Mapped[str | None] = mapped_column(String(30), nullable=True)
    query_params: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
