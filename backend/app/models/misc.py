"""security_event, notification, system_setting tables (Section 7.2)."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import uuid_pk


class SecurityEvent(Base):
    __tablename__ = "security_event"
    __table_args__ = (
        Index("ix_security_event_account_time", "account_id", "event_time"),
    )

    event_id: Mapped[uuid.UUID] = uuid_pk("event_id")
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("account.account_id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    event_time: Mapped[datetime] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))


class Notification(Base):
    __tablename__ = "notification"

    notification_id: Mapped[uuid.UUID] = uuid_pk("notification_id")
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("app_user.user_id"), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    link: Mapped[str | None] = mapped_column(String(300), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))


class SystemSetting(Base):
    __tablename__ = "system_setting"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    updated_by: Mapped[str | None] = mapped_column(String(150), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
