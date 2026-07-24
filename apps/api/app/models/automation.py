from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk
from app.models.enums import AutomationActionType, AutomationTriggerType, NotificationType


class AutomationRule(Base, TimestampMixin):
    __tablename__ = "automation_rules"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "public_id", name="uq_automation_rules_org_public_id"
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    public_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    trigger_type: Mapped[AutomationTriggerType] = mapped_column(
        Enum(AutomationTriggerType, name="automation_trigger_type", native_enum=False, length=32),
        nullable=False,
        index=True,
    )
    conditions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    action_type: Mapped[AutomationActionType] = mapped_column(
        Enum(AutomationActionType, name="automation_action_type", native_enum=False, length=32),
        nullable=False,
    )
    action_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Simple run-count guard against loops/runaways — see Phase 5 spec 11.
    execution_count: Mapped[int] = mapped_column(nullable=False, default=0)
    last_executed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "public_id", name="uq_notifications_org_public_id"
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    public_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    notification_type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, name="notification_type", native_enum=False, length=32),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(String(1000), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource_public_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        index=True,
    )
