"""Incident case workflow: state machine, priorities, SLA dates (Section 10)."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.errors import ApiError
from app.models.case import CaseNote, FraudCase
from app.models.customer import Account, Customer
from app.models.user import AppUser
from app.services import notification_service

STATES = ("NEW", "ASSIGNED", "UNDER_INVESTIGATION", "ESCALATED", "RESOLVED", "CLOSED")


def _supervisor_only(user: AppUser, case: FraudCase) -> bool:
    return user.role_name == "supervisor"


def _analyst_own_or_supervisor(user: AppUser, case: FraudCase) -> bool:
    if user.role_name == "supervisor":
        return True
    return user.role_name == "analyst" and case.assigned_to == user.user_id


# (from_status, to_status) -> {who, requires_note, requires_assignee}
TRANSITIONS: dict[tuple[str, str], dict] = {
    ("ASSIGNED", "UNDER_INVESTIGATION"): {"who": _analyst_own_or_supervisor, "requires_note": False},
    ("UNDER_INVESTIGATION", "ESCALATED"): {"who": _analyst_own_or_supervisor, "requires_note": True},
    ("ESCALATED", "UNDER_INVESTIGATION"): {"who": _supervisor_only, "requires_note": True, "requires_assignee": True},
    ("UNDER_INVESTIGATION", "RESOLVED"): {"who": _analyst_own_or_supervisor, "requires_note": True, "requires_outcome": True},
    ("ESCALATED", "RESOLVED"): {"who": _supervisor_only, "requires_note": True, "requires_outcome": True},
    ("RESOLVED", "CLOSED"): {"who": _supervisor_only, "requires_note": False},
    ("RESOLVED", "UNDER_INVESTIGATION"): {"who": _supervisor_only, "requires_note": True},
    ("CLOSED", "UNDER_INVESTIGATION"): {"who": _supervisor_only, "requires_note": True},
}

# System-triggered escalation is not exposed through TRANSITIONS (only the
# SLA job calls system_escalate directly) but shares the same "reachable
# states" so allowed_transitions() for a human doesn't offer it.
SYSTEM_ESCALATABLE_FROM = ("NEW", "ASSIGNED", "UNDER_INVESTIGATION")


def allowed_transitions_for(user: AppUser, case: FraudCase) -> list[str]:
    result = []
    for (from_status, to_status), config in TRANSITIONS.items():
        if from_status != case.status:
            continue
        if not config["who"](user, case):
            continue
        result.append(to_status)
    return result


def _priority_rank(priority: str) -> int:
    return {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(priority, 4)


def compute_sla_dates(opened_at: datetime, priority: str, settings: dict) -> tuple[datetime, datetime]:
    sla = settings["sla"][priority]
    ack_due = opened_at + timedelta(minutes=sla["ack_minutes"])
    resolve_due = opened_at + timedelta(minutes=sla["resolve_minutes"])
    return ack_due, resolve_due


def sla_state(case: FraudCase, now: datetime | None = None) -> str:
    if case.status in ("RESOLVED", "CLOSED"):
        return "ok"
    now = now or datetime.now(timezone.utc)
    due = case.resolve_due_at if case.acknowledged_at else case.ack_due_at
    if now > due:
        return "breached"
    total_window = (due - case.opened_at).total_seconds()
    remaining = (due - now).total_seconds()
    if total_window > 0 and remaining / total_window < 0.25:
        return "due_soon"
    return "ok"


def next_case_number(db: Session, opened_at: datetime) -> str:
    seq = db.execute(select(func.nextval("fraud_case_seq"))).scalar()
    return f"FC-{opened_at.year}-{seq:06d}"


def _least_loaded_analyst(db: Session) -> AppUser | None:
    from app.models.user import Role

    open_statuses = ("NEW", "ASSIGNED", "UNDER_INVESTIGATION", "ESCALATED")
    subq = (
        select(FraudCase.assigned_to, func.count(FraudCase.case_id).label("n"))
        .where(FraudCase.status.in_(open_statuses), FraudCase.assigned_to.is_not(None))
        .group_by(FraudCase.assigned_to)
        .subquery()
    )
    rows = db.execute(
        select(AppUser, subq.c.n)
        .join(Role, Role.role_id == AppUser.role_id)
        .outerjoin(subq, subq.c.assigned_to == AppUser.user_id)
        .where(Role.name == "analyst", AppUser.is_active.is_(True))
    ).all()
    if not rows:
        return None
    rows.sort(key=lambda r: (r[1] or 0))
    return rows[0][0]


def create_case_from_alert(
    db: Session,
    *,
    alert,
    txn,
    prediction,
    settings: dict,
    top_factors: list[dict],
) -> FraudCase:
    amount = Decimal(str(txn.amount))
    critical_amount = Decimal(str(settings["critical_amount_ngn"]))
    priority = "critical" if amount >= critical_amount else "high"

    account = db.get(Account, txn.account_id)
    opened_at = datetime.now(timezone.utc)
    ack_due, resolve_due = compute_sla_dates(opened_at, priority, settings)
    case_number = next_case_number(db, opened_at)

    assigned_to = None
    status = "NEW"
    if settings.get("auto_assign"):
        analyst = _least_loaded_analyst(db)
        if analyst is not None:
            assigned_to = analyst.user_id
            status = "ASSIGNED"

    last4 = account.account_number[-4:] if account else "????"
    case = FraudCase(
        case_number=case_number,
        alert_id=alert.alert_id,
        txn_id=txn.txn_id,
        source="ALERT",
        title=f"High-risk {txn.channel} {txn.txn_type} of ₦{amount:,.2f} on account ****{last4}",
        description="Automatically opened from a high-risk transaction alert.",
        assigned_to=assigned_to,
        priority=priority,
        status=status,
        amount_at_risk=amount,
        ack_due_at=ack_due,
        resolve_due_at=resolve_due,
        opened_at=opened_at,
        created_by=None,
    )
    db.add(case)
    db.flush()

    factor_summary = "; ".join(f"{f['label']}: {f['description']}" for f in top_factors[:3])
    db.add(CaseNote(
        case_id=case.case_id,
        user_id=None,
        note=(
            f"Case opened automatically. fraud_score={float(prediction.fraud_score):.4f}, "
            f"risk_band={prediction.risk_band}. Top factors: {factor_summary}"
        ),
        note_type="SYSTEM",
    ))
    audit(db, action="CASE_CREATED", entity="fraud_case", entity_id=str(case.case_id), actor="system",
          details={"source": "ALERT", "priority": priority, "status": status})

    if assigned_to:
        notification_service.notify_user(db, assigned_to, f"New {priority} case {case_number} assigned to you",
                                          link=f"/cases/{case.case_id}")
    else:
        notification_service.notify_role(db, "analyst", f"New {priority} case {case_number} needs an owner",
                                          link=f"/cases/{case.case_id}")
        notification_service.notify_role(db, "supervisor", f"New {priority} case {case_number} needs an owner",
                                          link=f"/cases/{case.case_id}")

    return case


def create_manual_case(
    db: Session,
    *,
    source: str,
    title: str,
    description: str,
    account_number: str | None,
    txn_id: uuid.UUID | None,
    amount_at_risk: Decimal,
    priority: str,
    settings: dict,
    created_by: AppUser,
) -> FraudCase:
    opened_at = datetime.now(timezone.utc)
    ack_due, resolve_due = compute_sla_dates(opened_at, priority, settings)
    case_number = next_case_number(db, opened_at)

    case = FraudCase(
        case_number=case_number,
        alert_id=None,
        txn_id=txn_id,
        source=source,
        title=title,
        description=description,
        assigned_to=None,
        priority=priority,
        status="NEW",
        amount_at_risk=amount_at_risk,
        ack_due_at=ack_due,
        resolve_due_at=resolve_due,
        opened_at=opened_at,
        created_by=created_by.user_id,
    )
    db.add(case)
    db.flush()
    audit(db, action="CASE_CREATED", entity="fraud_case", entity_id=str(case.case_id), user=created_by,
          details={"source": source, "priority": priority})
    notification_service.notify_role(db, "supervisor", f"New manual case {case_number} needs assignment",
                                      link=f"/cases/{case.case_id}")
    return case


def assign(db: Session, case: FraudCase, assignee: AppUser, acting_user: AppUser) -> FraudCase:
    if assignee.role_name not in ("analyst", "supervisor") or not assignee.is_active:
        raise ApiError(422, "INVALID_ASSIGNEE", "Assignee must be an active analyst or supervisor")
    old_assignee = case.assigned_to
    case.assigned_to = assignee.user_id
    if case.status == "NEW":
        case.status = "ASSIGNED"
    db.add(CaseNote(case_id=case.case_id, user_id=acting_user.user_id,
                     note=f"Case assigned to {assignee.full_name}", note_type="ASSIGNMENT"))
    audit(db, action="CASE_ASSIGNED", entity="fraud_case", entity_id=str(case.case_id), user=acting_user,
          details={"from": str(old_assignee) if old_assignee else None, "to": str(assignee.user_id)})
    notification_service.notify_user(db, assignee.user_id, f"Case {case.case_number} assigned to you",
                                      link=f"/cases/{case.case_id}")
    return case


def transition(
    db: Session,
    case: FraudCase,
    *,
    to_status: str,
    note: str,
    acting_user: AppUser,
    outcome: str | None = None,
    fraud_type: str | None = None,
    amount_recovered: Decimal | None = None,
) -> FraudCase:
    key = (case.status, to_status)
    config = TRANSITIONS.get(key)
    if config is None:
        raise ApiError(409, "INVALID_TRANSITION", f"Cannot move a case from {case.status} to {to_status}")
    if not config["who"](acting_user, case):
        raise ApiError(403, "FORBIDDEN", "You are not allowed to perform this transition")
    if config.get("requires_note") and not note:
        raise ApiError(422, "NOTE_REQUIRED", "A note is required for this transition")
    if config.get("requires_assignee") and case.assigned_to is None:
        raise ApiError(409, "NO_ASSIGNEE", "This case has no assignee; assign it before returning it to investigation")
    if config.get("requires_outcome") and outcome not in ("confirmed_fraud", "false_positive"):
        raise ApiError(422, "OUTCOME_REQUIRED", "outcome must be 'confirmed_fraud' or 'false_positive'")

    from_status = case.status
    case.status = to_status

    if to_status == "UNDER_INVESTIGATION" and from_status == "ASSIGNED":
        case.acknowledged_at = datetime.now(timezone.utc)
    if to_status == "RESOLVED":
        case.resolved_at = datetime.now(timezone.utc)
        case.outcome = outcome
        if fraud_type:
            case.fraud_type = fraud_type
        if amount_recovered is not None:
            case.amount_recovered = amount_recovered
        _apply_resolution_side_effects(db, case)
    if to_status == "CLOSED":
        case.closed_at = datetime.now(timezone.utc)
    if from_status == "RESOLVED" and to_status == "UNDER_INVESTIGATION":
        case.resolved_at = None
    if from_status == "CLOSED" and to_status == "UNDER_INVESTIGATION":
        case.closed_at = None
        case.resolved_at = None
        now = datetime.now(timezone.utc)
        settings = _load_settings(db)
        _, case.resolve_due_at = compute_sla_dates(now, case.priority, settings)

    db.add(CaseNote(case_id=case.case_id, user_id=acting_user.user_id, note=note, note_type="STATUS_CHANGE"))
    audit(db, action="CASE_STATUS_CHANGED", entity="fraud_case", entity_id=str(case.case_id), user=acting_user,
          details={"from": from_status, "to": to_status, "outcome": outcome})

    _notify_for_transition(db, case, from_status, to_status)
    return case


def system_escalate(db: Session, case: FraudCase, breach_type: str) -> FraudCase:
    if case.status not in SYSTEM_ESCALATABLE_FROM:
        raise ApiError(409, "INVALID_TRANSITION", "Case is not in an escalatable state")
    from_status = case.status
    case.status = "ESCALATED"
    db.add(CaseNote(
        case_id=case.case_id, user_id=None,
        note=f"SLA breached ({breach_type}): automatically escalated by the system",
        note_type="SYSTEM",
    ))
    audit(db, action="CASE_STATUS_CHANGED", entity="fraud_case", entity_id=str(case.case_id), actor="system",
          details={"from": from_status, "to": "ESCALATED", "breach_type": breach_type})
    notification_service.notify_role(db, "supervisor", f"Case {case.case_number} escalated: SLA breach ({breach_type})",
                                      link=f"/cases/{case.case_id}")
    return case


def _load_settings(db: Session) -> dict:
    from app.services.settings_service import get_settings_dict

    return get_settings_dict(db)


def _apply_resolution_side_effects(db: Session, case: FraudCase) -> None:
    from app.models.transaction import Txn

    if case.txn_id is not None:
        txn = db.get(Txn, case.txn_id)
        # Not guarded to "only if currently HELD": a case can be reopened
        # and resolved a second time with a different outcome (e.g. an
        # earlier confirmed_fraud finding overturned to false_positive), and
        # the transaction's status must follow the latest outcome.
        if txn is not None:
            txn.status = "DECLINED" if case.outcome == "confirmed_fraud" else "APPROVED"

    if case.outcome == "confirmed_fraud" and case.txn_id is not None:
        txn = db.get(Txn, case.txn_id)
        if txn is not None:
            account = db.get(Account, txn.account_id)
            if account is not None:
                customer = db.get(Customer, account.customer_id)
                if customer is not None:
                    customer.risk_profile = "high"


def _notify_for_transition(db: Session, case: FraudCase, from_status: str, to_status: str) -> None:
    if to_status == "ESCALATED":
        notification_service.notify_role(db, "supervisor", f"Case {case.case_number} escalated",
                                          link=f"/cases/{case.case_id}")
    elif from_status == "ESCALATED" and to_status == "UNDER_INVESTIGATION" and case.assigned_to:
        notification_service.notify_user(db, case.assigned_to, f"Case {case.case_number} returned to you",
                                          link=f"/cases/{case.case_id}")
    elif to_status == "RESOLVED":
        notification_service.notify_role(db, "supervisor", f"Case {case.case_number} resolved, awaiting closure",
                                          link=f"/cases/{case.case_id}")
    elif from_status == "CLOSED" and to_status == "UNDER_INVESTIGATION" and case.assigned_to:
        notification_service.notify_user(db, case.assigned_to, f"Case {case.case_number} reopened",
                                          link=f"/cases/{case.case_id}")
