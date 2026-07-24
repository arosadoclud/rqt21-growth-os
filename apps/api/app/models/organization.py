from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from app.models.membership import Membership


class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False, default="DO")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="America/Santo_Domingo")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")


    memberships: Mapped[list[Membership]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
