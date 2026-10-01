"""Load an account's recent history and compute the 23 features for one
transaction, online (Section 5.1, Section 7.4). Exactly four small queries.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.models.customer import Account
from app.models.misc import SecurityEvent
from app.models.transaction import Txn
from fraud_core.constants import ROLLING_WINDOW_DAYS, SECURITY_EVENT_WINDOW_HOURS
from fraud_core.features import compute_features_online


def load_history(db: Session, account_id, T: datetime) -> list[dict]:
    """Query 1: account's transactions with txn_time in [T-30d, T)."""
    lower = T - timedelta(days=ROLLING_WINDOW_DAYS)
    rows = db.execute(
        select(Txn.amount, Txn.txn_time, Txn.location, Txn.device_id, Txn.beneficiary_account)
        .where(Txn.account_id == account_id, Txn.txn_time >= lower, Txn.txn_time < T)
    ).all()
    return [
        {
            "amount": float(r.amount),
            "txn_time": r.txn_time,
            "location": r.location,
            "device_id": r.device_id,
            "beneficiary_account": r.beneficiary_account,
        }
        for r in rows
    ]


def device_seen_before(db: Session, account_id, device_id: str | None, T: datetime) -> bool:
    """Query 2: has device_id been used before T by this account?"""
    if not device_id:
        return False
    stmt = select(
        exists().where(Txn.account_id == account_id, Txn.device_id == device_id, Txn.txn_time < T)
    )
    return bool(db.execute(stmt).scalar())


def beneficiary_seen_before(db: Session, account_id, beneficiary_account: str | None, T: datetime) -> bool:
    """Query 3: has beneficiary_account been paid before T by this account?"""
    if not beneficiary_account:
        return False
    stmt = select(
        exists().where(
            Txn.account_id == account_id,
            Txn.beneficiary_account == beneficiary_account,
            Txn.txn_time < T,
        )
    )
    return bool(db.execute(stmt).scalar())


def load_security_events(db: Session, account_id, T: datetime) -> list[dict]:
    """Query 4: security events of the account in [T-48h, T]."""
    lower = T - timedelta(hours=SECURITY_EVENT_WINDOW_HOURS)
    rows = db.execute(
        select(SecurityEvent.event_time)
        .where(SecurityEvent.account_id == account_id, SecurityEvent.event_time >= lower, SecurityEvent.event_time <= T)
    ).all()
    return [{"event_time": r.event_time} for r in rows]


def compute_features_for_txn(db: Session, account: Account, txn: dict, global_median: float) -> dict:
    T = txn["txn_time"]
    history_txns = load_history(db, account.account_id, T)
    dev_seen = device_seen_before(db, account.account_id, txn.get("device_id"), T)
    ben_seen = beneficiary_seen_before(db, account.account_id, txn.get("beneficiary_account"), T)
    security_events = load_security_events(db, account.account_id, T)
    return compute_features_online(
        txn,
        history_txns,
        security_events,
        {"opened_on": account.opened_on},
        global_median,
        device_seen_before=dev_seen,
        beneficiary_seen_before=ben_seen,
    )
