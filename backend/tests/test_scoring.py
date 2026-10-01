"""Score endpoint: low/medium/high, idempotency, 503 without an active
model, alert/case/notification/audit side effects (Section 15.3).
"""
from __future__ import annotations

from datetime import datetime, timezone

from tests.conftest import make_account

API_KEY_HEADERS = {"X-API-Key": "test-api-key"}


def _score(client, **overrides):
    payload = {
        "txn_ref": overrides.pop("txn_ref", "TEST-REF-0001"),
        "account_number": "2000000001",
        "amount": "1000.00",
        "channel": "NIP",
        "txn_type": "TRANSFER",
        "txn_time": datetime.now(timezone.utc).isoformat(),
        "beneficiary_account": "9990001111",
        "beneficiary_bank": "058",
        "device_id": "dev-1",
        "location": "Lagos",
        "balance_before": "500000.00",
    }
    payload.update(overrides)
    return client.post("/api/v1/transactions/score", json=payload, headers=API_KEY_HEADERS)


def test_score_returns_503_without_active_model(client, db_session):
    make_account(db_session)
    resp = _score(client)
    assert resp.status_code == 503
    assert resp.json()["code"] == "NO_ACTIVE_MODEL"


def test_score_unknown_account_returns_404(client, db_session, active_model):
    resp = _score(client, account_number="0000000000")
    assert resp.status_code == 404
    assert resp.json()["code"] == "ACCOUNT_NOT_FOUND"


def test_score_low_risk_approves(client, db_session, active_model):
    make_account(db_session)
    resp = _score(
        client, txn_ref="LOW-1", amount="1000.00", beneficiary_account="9990001111", balance_before="500000.00",
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["risk_band"] == "low"
    assert body["decision"] == "APPROVE"
    assert body["alert_id"] is None
    assert body["case_id"] is None


def test_score_high_risk_holds_and_opens_case(client, db_session, active_model):
    make_account(db_session, account_number="2000000002")
    resp = _score(
        client, txn_ref="HIGH-1", account_number="2000000002",
        amount="450000.00", beneficiary_account="9990009999", balance_before="500000.00",
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["risk_band"] == "high"
    assert body["decision"] == "HOLD"
    assert body["alert_id"] is not None
    assert body["case_id"] is not None
    assert body["case_number"].startswith("FC-")
    assert len(body["top_factors"]) <= 5

    from app.models.transaction import Txn

    txn = db_session.query(Txn).filter(Txn.txn_ref == "HIGH-1").one()
    assert txn.status == "HELD"


def test_score_idempotent_replay(client, db_session, active_model):
    make_account(db_session, account_number="2000000003")
    first = _score(client, txn_ref="IDEMP-1", account_number="2000000003")
    assert first.status_code == 200
    second = _score(client, txn_ref="IDEMP-1", account_number="2000000003")
    assert second.status_code == 200
    assert first.json()["txn_id"] == second.json()["txn_id"]
    assert first.json()["prediction_id"] == second.json()["prediction_id"]

    from app.models.transaction import Txn

    count = db_session.query(Txn).filter(Txn.txn_ref == "IDEMP-1").count()
    assert count == 1


def test_score_requires_api_key(client, db_session, active_model):
    make_account(db_session, account_number="2000000004")
    resp = client.post("/api/v1/transactions/score", json={
        "txn_ref": "NOKEY-1", "account_number": "2000000004", "amount": "1000.00", "channel": "NIP",
        "txn_type": "TRANSFER", "txn_time": datetime.now(timezone.utc).isoformat(),
        "beneficiary_account": "999", "beneficiary_bank": "058", "device_id": "dev-1",
        "location": "Lagos", "balance_before": "5000.00",
    })
    assert resp.status_code == 401
    assert resp.json()["code"] == "INVALID_API_KEY"


def test_security_event_endpoint(client, db_session, active_model):
    make_account(db_session, account_number="2000000005")
    resp = client.post(
        "/api/v1/security-events",
        json={"account_number": "2000000005", "event_type": "SIM_SWAP",
              "event_time": datetime.now(timezone.utc).isoformat()},
        headers=API_KEY_HEADERS,
    )
    assert resp.status_code == 201
