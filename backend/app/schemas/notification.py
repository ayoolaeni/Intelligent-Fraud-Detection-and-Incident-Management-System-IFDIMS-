"""Notification schemas (Section 8.7)."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class NotificationOut(BaseModel):
    notification_id: uuid.UUID
    message: str
    link: str | None = None
    is_read: bool
    created_at: datetime
