"""role and app_user tables (Section 7.1)."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import uuid_pk

ROLE_NAMES = ("analyst", "supervisor", "admin")


class Role(Base):
    __tablename__ = "role"

    role_id: Mapped[uuid.UUID] = uuid_pk("role_id")
    name: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    permissions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    users: Mapped[list["AppUser"]] = relationship(back_populates="role")


class AppUser(Base):
    __tablename__ = "app_user"

    user_id: Mapped[uuid.UUID] = uuid_pk("user_id")
    role_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("role.role_id"), nullable=False)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    last_login_at: Mapped[datetime | None] = mapped_column(nullable=True)

    role: Mapped[Role] = relationship(back_populates="users")

    @property
    def role_name(self) -> str:
        return self.role.name if self.role else ""
