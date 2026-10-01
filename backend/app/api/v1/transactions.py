"""Transaction scoring and read endpoints (Section 8.2)."""
from __future__ import annotations

import time
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.errors import ApiError
from app.core.masking import mask_account_number, mask_phone
from app.core.rate_limit import scoring_rate_limiter
from app.core.rbac import require_api_key, require_roles
from app.db import get_db
from app.models.case import Alert, CaseNote, FraudCase
from app.models.customer import Account, Customer
from app.models.ml import ModelVersion, Prediction
from app.models.transaction import Txn
from app.models.user import AppUser
from app.schemas.common import Page
from app.schemas.transaction import (
    CustomerSummary,
    ReleaseDeclineRequest,
    ScoreTransactionRequest,
    ScoreTransactionResponse,
    SecurityEventRequest,
    TopFactor,
    TransactionDetailOut,
    TransactionOut,
)
from app.services import alert_service, case_service, feature_service, scoring_service
from app.services.model_registry import model_registry
from app.services.settings_service import get_settings_dict

router = APIRouter(tags=["transactions"])


def _txn_out(txn: Txn, account: Account, prediction: Prediction | None) -> TransactionOut:
    return TransactionOut(
        txn_id=txn.txn_id,
        txn_ref=txn.txn_ref,
        account_number_masked=mask_account_number(account.account_number),
        amount=txn.amount,
        channel=txn.channel,
        txn_type=txn.txn_type,
        txn_time=txn.txn_time,
        location=txn.location,
        status=txn.status,
        fraud_score=float(prediction.fraud_score) if prediction else None,
        risk_band=prediction.risk_band if prediction else None,
    )


def _existing_score_response(db: Session, txn: Txn) -> ScoreTransactionResponse:
    prediction = db.query(Prediction).filter(Prediction.txn_id == txn.txn_id).one_or_none()
    if prediction is None:
        raise ApiError(500, "INCONSISTENT_STATE", "Transaction exists without a prediction")
    alert = db.query(Alert).filter(Alert.prediction_id == prediction.prediction_id).one_or_none()
    case = None
    if alert is not None:
        case = db.query(FraudCase).filter(FraudCase.alert_id == alert.alert_id).one_or_none()
    model_row = db.get(ModelVersion, prediction.model_id)
    decision = "HOLD" if txn.status == "HELD" else "APPROVE"
    return ScoreTransactionResponse(
        txn_id=txn.txn_id,
        prediction_id=prediction.prediction_id,
        fraud_score=float(prediction.fraud_score),
        risk_band=prediction.risk_band,
        decision=decision,
        alert_id=alert.alert_id if alert else None,
        case_id=case.case_id if case else None,
        case_number=case.case_number if case else None,
        top_factors=[TopFactor(**f) for f in prediction.shap_values],
        model_version=model_row.version if model_row else "unknown",
        latency_ms=float(prediction.latency_ms),
    )


@router.post("/transactions/score", response_model=ScoreTransactionResponse)
def score_transaction(
    payload: ScoreTransactionRequest,
    api_key_name: str = Depends(require_api_key),
    db: Session = Depends(get_db),
) -> ScoreTransactionResponse:
    scoring_rate_limiter.check(api_key_name)

    existing = db.query(Txn).filter(Txn.txn_ref == payload.txn_ref).one_or_none()
    if existing is not None:
        return _existing_score_response(db, existing)

    account = db.query(Account).filter(Account.account_number == payload.account_number).one_or_none()
    if account is None:
        raise ApiError(404, "ACCOUNT_NOT_FOUND", "Unknown account_number")

    loaded_model = model_registry.loaded
    if loaded_model is None:
        raise ApiError(503, "NO_ACTIVE_MODEL", "No active model is available for scoring")

    settings = get_settings_dict(db)

    txn_dict = {
        "amount": float(payload.amount),
        "channel": payload.channel,
        "txn_type": payload.txn_type,
        "txn_time": payload.txn_time,
        "beneficiary_account": payload.beneficiary_account,
        "device_id": payload.device_id,
        "location": payload.location,
        "balance_before": float(payload.balance_before),
    }

    start = time.perf_counter()
    features = feature_service.compute_features_for_txn(db, account, txn_dict, loaded_model.global_median_amount)
    fraud_score, top_factors = scoring_service.score_and_explain(loaded_model, features)
    latency_ms = (time.perf_counter() - start) * 1000

    band = scoring_service.band_for_score(
        fraud_score, settings["risk_threshold_medium"], settings["risk_threshold_high"]
    )

    txn = Txn(
        txn_ref=payload.txn_ref,
        account_id=account.account_id,
        amount=payload.amount,
        channel=payload.channel,
        txn_type=payload.txn_type,
        txn_time=payload.txn_time,
        beneficiary_account=payload.beneficiary_account,
        beneficiary_bank=payload.beneficiary_bank,
        device_id=payload.device_id,
        location=payload.location,
        balance_before=payload.balance_before,
        status="APPROVED",
    )
    db.add(txn)
    db.flush()

    prediction = Prediction(
        txn_id=txn.txn_id,
        model_id=uuid.UUID(loaded_model.model_id),
        fraud_score=round(fraud_score, 4),
        risk_band=band,
        shap_values=top_factors,
        features=features,
        latency_ms=round(latency_ms, 2),
    )
    db.add(prediction)
    db.flush()

    alert_id = None
    case = None
    decision = "APPROVE"

    if band == "medium":
        alert = alert_service.create_alert(db, prediction, severity="medium")
        alert_id = alert.alert_id
    elif band == "high":
        alert = alert_service.create_alert(db, prediction, severity="high")
        alert_id = alert.alert_id
        if settings.get("hold_high_risk", True):
            txn.status = "HELD"
            decision = "HOLD"
        case = case_service.create_case_from_alert(
            db, alert=alert, txn=txn, prediction=prediction, settings=settings, top_factors=top_factors
        )
        # Deliberately left as "OPEN", not "CASE_OPENED": Section 8.3's
        # dismiss endpoint only works on OPEN alerts and is how an analyst
        # fast-tracks a false positive (releasing the held transaction)
        # even though a case was already auto-created. "CASE_OPENED" is for
        # the manual /alerts/{id}/open-case flow (Section 8.3), where no
        # case exists until an analyst decides to create one.

    audit(db, action="TXN_SCORED", entity="txn", entity_id=str(txn.txn_id), actor=f"api:{api_key_name}",
          details={"fraud_score": float(fraud_score), "risk_band": band, "decision": decision})
    db.commit()

    return ScoreTransactionResponse(
        txn_id=txn.txn_id,
        prediction_id=prediction.prediction_id,
        fraud_score=round(fraud_score, 4),
        risk_band=band,
        decision=decision,
        alert_id=alert_id,
        case_id=case.case_id if case else None,
        case_number=case.case_number if case else None,
        top_factors=[TopFactor(**f) for f in top_factors],
        model_version=loaded_model.version,
        latency_ms=round(latency_ms, 2),
    )


@router.post("/security-events", status_code=201)
def create_security_event(
    payload: SecurityEventRequest,
    api_key_name: str = Depends(require_api_key),
    db: Session = Depends(get_db),
) -> dict:
    from app.models.misc import SecurityEvent

    account = db.query(Account).filter(Account.account_number == payload.account_number).one_or_none()
    if account is None:
        raise ApiError(404, "ACCOUNT_NOT_FOUND", "Unknown account_number")

    db.add(SecurityEvent(account_id=account.account_id, event_type=payload.event_type, event_time=payload.event_time))
    audit(db, action="SECURITY_EVENT_RECEIVED", entity="security_event", entity_id=payload.account_number,
          actor=f"api:{api_key_name}", details={"event_type": payload.event_type})
    db.commit()
    return {"detail": "recorded"}


@router.get("/transactions", response_model=Page[TransactionOut])
def list_transactions(
    account_number: str | None = None,
    channel: str | None = None,
    risk_band: str | None = None,
    status: str | None = None,
    from_: datetime | None = Query(None, alias="from"),
    to: datetime | None = None,
    min_amount: float | None = None,
    page: int = 1,
    page_size: int = 25,
    user: AppUser = Depends(require_roles("analyst", "supervisor", "admin")),
    db: Session = Depends(get_db),
) -> Page[TransactionOut]:
    page_size = min(page_size, 100)
    query = select(Txn, Account, Prediction).join(Account, Account.account_id == Txn.account_id).outerjoin(
        Prediction, Prediction.txn_id == Txn.txn_id
    )
    if account_number:
        query = query.where(Account.account_number == account_number)
    if channel:
        query = query.where(Txn.channel == channel)
    if risk_band:
        query = query.where(Prediction.risk_band == risk_band)
    if status:
        query = query.where(Txn.status == status)
    if from_:
        query = query.where(Txn.txn_time >= from_)
    if to:
        query = query.where(Txn.txn_time <= to)
    if min_amount:
        query = query.where(Txn.amount >= min_amount)

    total_count = db.execute(select(func.count()).select_from(query.subquery())).scalar_one()

    query = query.order_by(Txn.txn_time.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = db.execute(query).all()
    items = [_txn_out(txn, account, prediction) for txn, account, prediction in rows]
    return Page(items=items, total=total_count, page=page, page_size=page_size)


@router.get("/transactions/{txn_id}", response_model=TransactionDetailOut)
def get_transaction(
    txn_id: uuid.UUID,
    user: AppUser = Depends(require_roles("analyst", "supervisor", "admin")),
    db: Session = Depends(get_db),
) -> TransactionDetailOut:
    txn = db.get(Txn, txn_id)
    if txn is None:
        raise ApiError(404, "NOT_FOUND", "Transaction not found")
    account = db.get(Account, txn.account_id)
    customer = db.get(Customer, account.customer_id) if account else None
    prediction = db.query(Prediction).filter(Prediction.txn_id == txn.txn_id).one_or_none()

    alert = None
    case = None
    if prediction is not None:
        alert = db.query(Alert).filter(Alert.prediction_id == prediction.prediction_id).one_or_none()
        if alert is not None:
            case = db.query(FraudCase).filter(FraudCase.alert_id == alert.alert_id).one_or_none()

    recent = []
    if account is not None:
        recent_rows = db.execute(
            select(Txn, Prediction)
            .outerjoin(Prediction, Prediction.txn_id == Txn.txn_id)
            .where(Txn.account_id == account.account_id)
            .order_by(Txn.txn_time.desc())
            .limit(20)
        ).all()
        recent = [_txn_out(t, account, p) for t, p in recent_rows]

    customer_summary = None
    if customer is not None and account is not None:
        age_days = (datetime.now().date() - account.opened_on).days
        customer_summary = CustomerSummary(
            customer_id=customer.customer_id,
            full_name=customer.full_name,
            phone_masked=mask_phone(customer.phone_last4),
            risk_profile=customer.risk_profile,
            account_age_days=float(age_days),
        )

    return TransactionDetailOut(
        txn=_txn_out(txn, account, prediction),
        prediction={"fraud_score": float(prediction.fraud_score), "risk_band": prediction.risk_band,
                    "top_factors": prediction.shap_values, "features": prediction.features} if prediction else None,
        alert_id=alert.alert_id if alert else None,
        case_id=case.case_id if case else None,
        case_number=case.case_number if case else None,
        customer=customer_summary,
        recent_transactions=recent,
    )


def _check_release_decline_permission(db: Session, txn: Txn, user: AppUser) -> FraudCase | None:
    prediction = db.query(Prediction).filter(Prediction.txn_id == txn.txn_id).one_or_none()
    case = None
    if prediction is not None:
        alert = db.query(Alert).filter(Alert.prediction_id == prediction.prediction_id).one_or_none()
        if alert is not None:
            case = db.query(FraudCase).filter(FraudCase.alert_id == alert.alert_id).one_or_none()
    if user.role_name == "supervisor":
        return case
    if user.role_name == "analyst" and case is not None and case.assigned_to == user.user_id:
        return case
    raise ApiError(403, "FORBIDDEN", "Only the assigned analyst or a supervisor may release/decline this transaction")


@router.post("/transactions/{txn_id}/release")
def release_transaction(
    txn_id: uuid.UUID,
    payload: ReleaseDeclineRequest,
    user: AppUser = Depends(require_roles("analyst", "supervisor")),
    db: Session = Depends(get_db),
) -> dict:
    txn = db.get(Txn, txn_id)
    if txn is None:
        raise ApiError(404, "NOT_FOUND", "Transaction not found")
    if txn.status != "HELD":
        raise ApiError(409, "NOT_HELD", "Only held transactions can be released")
    case = _check_release_decline_permission(db, txn, user)
    txn.status = "APPROVED"
    if case is not None:
        db.add(CaseNote(case_id=case.case_id, user_id=user.user_id, note=f"Transaction released: {payload.reason}",
                         note_type="NOTE"))
    audit(db, action="TXN_RELEASED", entity="txn", entity_id=str(txn.txn_id), user=user, details={"reason": payload.reason})
    db.commit()
    return {"detail": "Transaction released"}


@router.post("/transactions/{txn_id}/decline")
def decline_transaction(
    txn_id: uuid.UUID,
    payload: ReleaseDeclineRequest,
    user: AppUser = Depends(require_roles("analyst", "supervisor")),
    db: Session = Depends(get_db),
) -> dict:
    txn = db.get(Txn, txn_id)
    if txn is None:
        raise ApiError(404, "NOT_FOUND", "Transaction not found")
    if txn.status != "HELD":
        raise ApiError(409, "NOT_HELD", "Only held transactions can be declined")
    case = _check_release_decline_permission(db, txn, user)
    txn.status = "DECLINED"
    if case is not None:
        db.add(CaseNote(case_id=case.case_id, user_id=user.user_id, note=f"Transaction declined: {payload.reason}",
                         note_type="NOTE"))
    audit(db, action="TXN_DECLINED", entity="txn", entity_id=str(txn.txn_id), user=user, details={"reason": payload.reason})
    db.commit()
    return {"detail": "Transaction declined"}
