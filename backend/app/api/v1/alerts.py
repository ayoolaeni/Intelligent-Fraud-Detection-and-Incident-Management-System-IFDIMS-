"""Alert endpoints (Section 8.3)."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.masking import mask_account_number, mask_phone
from app.core.rbac import require_roles
from app.db import get_db
from app.models.case import Alert, FraudCase
from app.models.customer import Account, Customer
from app.models.ml import Prediction
from app.models.transaction import Txn
from app.models.user import AppUser
from app.schemas.alert import AlertDetailOut, AlertOut, DismissAlertRequest
from app.schemas.common import Page
from app.schemas.transaction import CustomerSummary, TopFactor, TransactionOut
from app.services import alert_service
from app.services.settings_service import get_settings_dict

router = APIRouter(prefix="/alerts", tags=["alerts"])


def _alert_out(alert: Alert, prediction: Prediction, txn: Txn, account: Account) -> AlertOut:
    case = None
    return AlertOut(
        alert_id=alert.alert_id,
        txn_id=txn.txn_id,
        account_number_masked=mask_account_number(account.account_number),
        channel=txn.channel,
        amount=txn.amount,
        fraud_score=float(prediction.fraud_score),
        risk_band=prediction.risk_band,
        severity=alert.severity,
        status=alert.status,
        created_at=alert.created_at,
        case_id=case,
    )


@router.get("", response_model=Page[AlertOut])
def list_alerts(
    status: str = "OPEN",
    severity: str | None = None,
    channel: str | None = None,
    from_: datetime | None = None,
    to: datetime | None = None,
    sort: str = "created_at",
    page: int = 1,
    page_size: int = 25,
    user: AppUser = Depends(require_roles("analyst", "supervisor")),
    db: Session = Depends(get_db),
) -> Page[AlertOut]:
    page_size = min(page_size, 100)
    query = (
        select(Alert, Prediction, Txn, Account)
        .join(Prediction, Prediction.prediction_id == Alert.prediction_id)
        .join(Txn, Txn.txn_id == Prediction.txn_id)
        .join(Account, Account.account_id == Txn.account_id)
    )
    if status:
        query = query.where(Alert.status == status)
    if severity:
        query = query.where(Alert.severity == severity)
    if channel:
        query = query.where(Txn.channel == channel)
    if from_:
        query = query.where(Alert.created_at >= from_)
    if to:
        query = query.where(Alert.created_at <= to)

    total = db.execute(select(func.count()).select_from(query.subquery())).scalar_one()

    order_col = Prediction.fraud_score if sort == "fraud_score" else Alert.created_at
    query = query.order_by(order_col.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = db.execute(query).all()
    items = [_alert_out(a, p, t, acc) for a, p, t, acc in rows]
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.get("/{alert_id}", response_model=AlertDetailOut)
def get_alert(
    alert_id: uuid.UUID,
    user: AppUser = Depends(require_roles("analyst", "supervisor")),
    db: Session = Depends(get_db),
) -> AlertDetailOut:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise ApiError(404, "NOT_FOUND", "Alert not found")
    prediction = db.get(Prediction, alert.prediction_id)
    txn = db.get(Txn, prediction.txn_id)
    account = db.get(Account, txn.account_id)
    customer = db.get(Customer, account.customer_id) if account else None

    recent_rows = db.execute(
        select(Txn, Prediction)
        .outerjoin(Prediction, Prediction.txn_id == Txn.txn_id)
        .where(Txn.account_id == account.account_id)
        .order_by(Txn.txn_time.desc())
        .limit(20)
    ).all()
    recent = [
        TransactionOut(
            txn_id=t.txn_id, txn_ref=t.txn_ref, account_number_masked=mask_account_number(account.account_number),
            amount=t.amount, channel=t.channel, txn_type=t.txn_type, txn_time=t.txn_time, location=t.location,
            status=t.status, fraud_score=float(p.fraud_score) if p else None, risk_band=p.risk_band if p else None,
        )
        for t, p in recent_rows
    ]

    customer_summary = None
    if customer is not None:
        age_days = (datetime.now().date() - account.opened_on).days
        customer_summary = CustomerSummary(
            customer_id=customer.customer_id, full_name=customer.full_name,
            phone_masked=mask_phone(customer.phone_last4), risk_profile=customer.risk_profile,
            account_age_days=float(age_days),
        )

    return AlertDetailOut(
        alert=_alert_out(alert, prediction, txn, account),
        txn=TransactionOut(
            txn_id=txn.txn_id, txn_ref=txn.txn_ref, account_number_masked=mask_account_number(account.account_number),
            amount=txn.amount, channel=txn.channel, txn_type=txn.txn_type, txn_time=txn.txn_time,
            location=txn.location, status=txn.status, fraud_score=float(prediction.fraud_score),
            risk_band=prediction.risk_band,
        ),
        top_factors=[TopFactor(**f) for f in prediction.shap_values],
        customer=customer_summary,
        recent_transactions=recent,
    )


@router.post("/{alert_id}/dismiss")
def dismiss_alert(
    alert_id: uuid.UUID,
    payload: DismissAlertRequest,
    user: AppUser = Depends(require_roles("analyst", "supervisor")),
    db: Session = Depends(get_db),
) -> dict:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise ApiError(404, "NOT_FOUND", "Alert not found")
    alert_service.dismiss(db, alert, payload.reason, user)
    db.commit()
    return {"detail": "Alert dismissed"}


@router.post("/{alert_id}/open-case")
def open_case(
    alert_id: uuid.UUID,
    user: AppUser = Depends(require_roles("analyst", "supervisor")),
    db: Session = Depends(get_db),
) -> dict:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise ApiError(404, "NOT_FOUND", "Alert not found")
    settings = get_settings_dict(db)
    case = alert_service.open_case_from_alert(db, alert, user, settings)
    db.commit()
    return {"case_id": str(case.case_id), "case_number": case.case_number}
