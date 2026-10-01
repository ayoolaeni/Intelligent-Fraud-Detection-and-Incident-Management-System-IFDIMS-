"""Alert lifecycle: create, dismiss, open a case from a medium alert
(Section 8.3).
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.errors import ApiError
from app.models.case import Alert
from app.models.ml import Prediction
from app.models.transaction import Txn
from app.models.user import AppUser
from app.services import case_service


def create_alert(db: Session, prediction: Prediction, severity: str) -> Alert:
    alert = Alert(prediction_id=prediction.prediction_id, severity=severity, status="OPEN")
    db.add(alert)
    db.flush()
    return alert


def dismiss(db: Session, alert: Alert, reason: str, acting_user: AppUser) -> Alert:
    if alert.status != "OPEN":
        raise ApiError(409, "ALERT_NOT_OPEN", "Only open alerts can be dismissed")

    alert.status = "DISMISSED"
    alert.dismiss_reason = reason
    alert.reviewed_by = acting_user.user_id
    alert.reviewed_at = datetime.now(timezone.utc)

    prediction = db.get(Prediction, alert.prediction_id)
    txn = db.get(Txn, prediction.txn_id) if prediction else None
    if txn is not None and txn.status == "HELD":
        txn.status = "APPROVED"

    audit(db, action="ALERT_DISMISSED", entity="alert", entity_id=str(alert.alert_id), user=acting_user,
          details={"reason": reason})
    return alert


def open_case_from_alert(db: Session, alert: Alert, acting_user: AppUser, settings: dict) -> "case_service.FraudCase":
    if alert.status != "OPEN":
        raise ApiError(409, "ALERT_NOT_OPEN", "Only open alerts can be turned into a case")
    if alert.severity != "medium":
        raise ApiError(409, "NOT_MEDIUM_ALERT", "Only medium-severity alerts are opened into a case manually")

    prediction = db.get(Prediction, alert.prediction_id)
    txn = db.get(Txn, prediction.txn_id)
    amount = Decimal(str(txn.amount))
    critical_amount = Decimal(str(settings["critical_amount_ngn"]))
    priority = "high" if amount >= critical_amount else "medium"

    from app.models.customer import Account

    account = db.get(Account, txn.account_id)
    last4 = account.account_number[-4:] if account else "????"

    opened_at = datetime.now(timezone.utc)
    ack_due, resolve_due = case_service.compute_sla_dates(opened_at, priority, settings)
    case_number = case_service.next_case_number(db, opened_at)

    from app.models.case import CaseNote, FraudCase

    case = FraudCase(
        case_number=case_number,
        alert_id=alert.alert_id,
        txn_id=txn.txn_id,
        source="ALERT",
        title=f"Medium-risk {txn.channel} {txn.txn_type} of ₦{amount:,.2f} on account ****{last4}",
        description="Opened by an analyst from a medium-risk alert.",
        priority=priority,
        status="NEW",
        amount_at_risk=amount,
        ack_due_at=ack_due,
        resolve_due_at=resolve_due,
        opened_at=opened_at,
        created_by=acting_user.user_id,
    )
    db.add(case)
    db.flush()
    db.add(CaseNote(case_id=case.case_id, user_id=acting_user.user_id,
                     note=f"Case opened from medium alert (score={float(prediction.fraud_score):.4f})",
                     note_type="SYSTEM"))

    alert.status = "CASE_OPENED"

    audit(db, action="CASE_CREATED", entity="fraud_case", entity_id=str(case.case_id), user=acting_user,
          details={"source": "ALERT", "priority": priority})
    return case
