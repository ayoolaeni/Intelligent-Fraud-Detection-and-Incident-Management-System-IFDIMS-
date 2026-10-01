"""In-app notifications (Section 11). No email/SMS (docs/DECISIONS.md D10);
designed so an EmailChannel could be added later without changing call
sites elsewhere in the codebase.
"""
from __future__ import annotations

import uuid
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.misc import Notification
from app.models.user import AppUser, Role


class NotificationChannel(Protocol):
    def send(self, db: Session, user_id: uuid.UUID, message: str, link: str | None) -> None: ...


class InAppChannel:
    def send(self, db: Session, user_id: uuid.UUID, message: str, link: str | None) -> None:
        db.add(Notification(user_id=user_id, message=message, link=link))


CHANNELS: list[NotificationChannel] = [InAppChannel()]


def notify_user(db: Session, user_id: uuid.UUID, message: str, *, link: str | None = None) -> None:
    for channel in CHANNELS:
        channel.send(db, user_id, message, link)


def notify_role(db: Session, role_name: str, message: str, *, link: str | None = None) -> None:
    user_ids = db.execute(
        select(AppUser.user_id)
        .join(Role, Role.role_id == AppUser.role_id)
        .where(Role.name == role_name, AppUser.is_active.is_(True))
    ).scalars().all()
    for user_id in user_ids:
        notify_user(db, user_id, message, link=link)
