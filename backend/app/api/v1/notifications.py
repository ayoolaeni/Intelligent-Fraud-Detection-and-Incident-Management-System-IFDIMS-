"""Notification endpoints (Section 8.7)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.rbac import get_current_user
from app.db import get_db
from app.models.misc import Notification
from app.models.user import AppUser
from app.schemas.notification import NotificationOut

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
def list_notifications(
    unread: bool = False,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[NotificationOut]:
    query = select(Notification).where(Notification.user_id == user.user_id)
    if unread:
        query = query.where(Notification.is_read.is_(False))
    query = query.order_by(Notification.created_at.desc()).limit(100)
    rows = db.execute(query).scalars().all()
    return [NotificationOut.model_validate(n, from_attributes=True) for n in rows]


@router.post("/{notification_id}/read")
def mark_read(
    notification_id: uuid.UUID,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    notification = db.get(Notification, notification_id)
    if notification is None or notification.user_id != user.user_id:
        raise ApiError(404, "NOT_FOUND", "Notification not found")
    notification.is_read = True
    db.commit()
    return {"detail": "Marked as read"}


@router.post("/read-all")
def mark_all_read(
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    db.execute(
        update(Notification).where(Notification.user_id == user.user_id).values(is_read=True)
    )
    db.commit()
    return {"detail": "All marked as read"}
