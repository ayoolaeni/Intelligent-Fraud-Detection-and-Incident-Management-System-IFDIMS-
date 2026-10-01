"""Append-only audit logging helper (Section 7.1 audit_log, FR10)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.user import AppUser


def audit(
    db: Session,
    *,
    action: str,
    entity: str,
    entity_id: str,
    user: AppUser | None = None,
    actor: str | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
) -> None:
    """Record an audit entry. Does not commit; the caller's transaction does.
    ``actor`` overrides the derived actor string (e.g. ``api:simulator`` or
    ``system``); when omitted it is taken from ``user.email`` or "system".
    """
    if actor is None:
        actor = user.email if user is not None else "system"
    db.add(
        AuditLog(
            user_id=user.user_id if user is not None else None,
            actor=actor,
            action=action,
            entity=entity,
            entity_id=str(entity_id),
            details=details or {},
            ip_address=ip_address,
        )
    )
