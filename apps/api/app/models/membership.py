from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User


class Role(str, enum.Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    MARKETER = "MARKETER"
    SALES = "SALES"
    ANALYST = "ANALYST"
    VIEWER = "VIEWER"


ROLE_RANK: dict[Role, int] = {
    Role.OWNER: 60,
    Role.ADMIN: 50,
    Role.MARKETER: 40,
    Role.SALES: 30,
    Role.ANALYST: 20,
    Role.VIEWER: 10,
}


def role_at_least(role: Role, minimum: Role) -> bool:
    return ROLE_RANK[role] >= ROLE_RANK[minimum]


class Membership(Base, TimestampMixin):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "organization_id", name="uq_memberships_user_org"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[Role] = mapped_column(
        Enum(Role, name="membership_role", native_enum=False, length=32),
        nullable=False,
    )

    user: Mapped[User] = relationship(back_populates="memberships")
    organization: Mapped[Organization] = relationship(back_populates="memberships")
