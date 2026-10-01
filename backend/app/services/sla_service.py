"""Scheduled SLA breach check (Section 10.4). Runs every 60s via APScheduler,
guarded by a PostgreSQL advisory lock so only one worker acts at a time.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.case import FraudCase
from app.services import case_service

logger = logging.getLogger("ifdims.sla")

ADVISORY_LOCK_KEY = 918_273_645
ACTIVE_STATUSES = ("NEW", "ASSIGNED", "UNDER_INVESTIGATION")


def run_sla_check() -> None:
    db: Session = SessionLocal()
    try:
        got_lock = db.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": ADVISORY_LOCK_KEY}).scalar()
        if not got_lock:
            return
        try:
            _check_breaches(db)
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("SLA check failed")
        finally:
            db.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": ADVISORY_LOCK_KEY})
    finally:
        db.close()


def _check_breaches(db: Session) -> None:
    """Single pass over all still-active cases so a case is escalated at
    most once per run, and never twice for the same breach (once escalated
    it leaves ACTIVE_STATUSES and is excluded from future runs' candidate
    set too).
    """
    now = datetime.now(timezone.utc)
    candidates = db.execute(
        select(FraudCase).where(FraudCase.status.in_(ACTIVE_STATUSES))
    ).scalars().all()

    for case in candidates:
        ack_breached = case.status in ("NEW", "ASSIGNED") and now > case.ack_due_at
        resolve_breached = now > case.resolve_due_at
        if ack_breached and resolve_breached:
            breach_type = "ack_and_resolve_overdue"
        elif ack_breached:
            breach_type = "ack_overdue"
        elif resolve_breached:
            breach_type = "resolve_overdue"
        else:
            continue
        case_service.system_escalate(db, case, breach_type=breach_type)
