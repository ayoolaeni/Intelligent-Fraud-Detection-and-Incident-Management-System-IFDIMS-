"""Full case workflow (Section 15.3): high-risk transaction -> case NEW ->
assign -> investigate -> escalate -> return -> resolve (confirmed fraud:
txn DECLINED, customer risk high) -> close -> reopen -> resolve (false
positive) -> close. Also alert dismissal releases a held transaction.
"""
from __future__ import annotations

from datetime import datetime, timezone

from tests.conftest import auth_headers, make_account, make_user

API_KEY_HEADERS = {"X-API-Key": "test-api-key"}


def _score_high_risk(client, account_number: str, txn_ref: str):
    payload = {
        "txn_ref": txn_ref, "account_number": account_number, "amount": "480000.00", "channel": "NIP",
        "txn_type": "TRANSFER", "txn_time": datetime.now(timezone.utc).isoformat(),
        "beneficiary_account": "9990009999", "beneficiary_bank": "058", "device_id": "dev-1",
        "location": "Lagos", "balance_before": "500000.00",
    }
    return client.post("/api/v1/transactions/score", json=payload, headers=API_KEY_HEADERS)


def test_full_case_lifecycle(client, db_session, roles, active_model):
    make_account(db_session, account_number="2100000001")
    supervisor = make_user(db_session, roles, "supervisor", "sup1@test.local")
    analyst = make_user(db_session, roles, "analyst", "an1@test.local")

    sup_headers = auth_headers(client, "sup1@test.local")
    an_headers = auth_headers(client, "an1@test.local")

    score_resp = _score_high_risk(client, "2100000001", "WF-1")
    assert score_resp.status_code == 200, score_resp.text
    case_id = score_resp.json()["case_id"]
    assert case_id is not None

    # Case starts NEW (auto_assign defaults to false)
    detail = client.get(f"/api/v1/cases/{case_id}", headers=sup_headers).json()
    assert detail["case"]["status"] == "NEW"

    # Assign (supervisor only)
    resp = client.post(f"/api/v1/cases/{case_id}/assign", json={"user_id": str(analyst.user_id)}, headers=sup_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "ASSIGNED"

    # Analyst cannot assign
    resp = client.post(f"/api/v1/cases/{case_id}/assign", json={"user_id": str(analyst.user_id)}, headers=an_headers)
    assert resp.status_code == 403

    # ASSIGNED -> UNDER_INVESTIGATION (assigned analyst)
    resp = client.post(f"/api/v1/cases/{case_id}/transition",
                        json={"to_status": "UNDER_INVESTIGATION", "note": "starting"}, headers=an_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "UNDER_INVESTIGATION"

    # UNDER_INVESTIGATION -> ESCALATED (requires note)
    resp = client.post(f"/api/v1/cases/{case_id}/transition",
                        json={"to_status": "ESCALATED", "note": ""}, headers=an_headers)
    assert resp.status_code == 422
    assert resp.json()["code"] == "NOTE_REQUIRED"

    resp = client.post(f"/api/v1/cases/{case_id}/transition",
                        json={"to_status": "ESCALATED", "note": "need supervisor input"}, headers=an_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ESCALATED"

    # ESCALATED -> UNDER_INVESTIGATION (supervisor only, since assignee still set)
    resp = client.post(f"/api/v1/cases/{case_id}/transition",
                        json={"to_status": "UNDER_INVESTIGATION", "note": "go ahead"}, headers=sup_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "UNDER_INVESTIGATION"

    # Invalid transition
    resp = client.post(f"/api/v1/cases/{case_id}/transition",
                        json={"to_status": "CLOSED", "note": "x"}, headers=an_headers)
    assert resp.status_code == 409
    assert resp.json()["code"] == "INVALID_TRANSITION"

    # UNDER_INVESTIGATION -> RESOLVED (confirmed fraud)
    resp = client.post(f"/api/v1/cases/{case_id}/transition", json={
        "to_status": "RESOLVED", "note": "confirmed with customer", "outcome": "confirmed_fraud",
        "fraud_type": "SOCIAL_ENGINEERING", "amount_recovered": "0",
    }, headers=an_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "RESOLVED"
    assert resp.json()["outcome"] == "confirmed_fraud"

    from app.models.customer import Account, Customer
    from app.models.transaction import Txn

    txn = db_session.query(Txn).filter(Txn.txn_ref == "WF-1").one()
    assert txn.status == "DECLINED"
    account = db_session.get(Account, txn.account_id)
    customer = db_session.get(Customer, account.customer_id)
    assert customer.risk_profile == "high"

    # RESOLVED -> CLOSED (supervisor only)
    resp = client.post(f"/api/v1/cases/{case_id}/transition",
                        json={"to_status": "CLOSED", "note": "closing"}, headers=an_headers)
    assert resp.status_code == 403

    resp = client.post(f"/api/v1/cases/{case_id}/transition",
                        json={"to_status": "CLOSED", "note": "closing"}, headers=sup_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "CLOSED"

    # CLOSED -> UNDER_INVESTIGATION (reopen)
    resp = client.post(f"/api/v1/cases/{case_id}/transition",
                        json={"to_status": "UNDER_INVESTIGATION", "note": "reopen for review"}, headers=sup_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "UNDER_INVESTIGATION"

    # Resolve again, this time false positive
    resp = client.post(f"/api/v1/cases/{case_id}/transition", json={
        "to_status": "RESOLVED", "note": "actually legitimate", "outcome": "false_positive",
    }, headers=an_headers)
    assert resp.status_code == 200
    assert resp.json()["outcome"] == "false_positive"

    txn = db_session.query(Txn).filter(Txn.txn_ref == "WF-1").one()
    assert txn.status == "APPROVED"

    resp = client.post(f"/api/v1/cases/{case_id}/transition",
                        json={"to_status": "CLOSED", "note": "closing again"}, headers=sup_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "CLOSED"

    # History has entries
    history = client.get(f"/api/v1/cases/{case_id}/history", headers=sup_headers).json()
    assert len(history) >= 5


def test_escalated_return_without_assignee_refused(client, db_session, roles, active_model):
    make_account(db_session, account_number="2100000002")
    supervisor = make_user(db_session, roles, "supervisor", "sup2@test.local")
    sup_headers = auth_headers(client, "sup2@test.local")

    score_resp = _score_high_risk(client, "2100000002", "WF-2")
    case_id = score_resp.json()["case_id"]

    # Manually drive it to ESCALATED without ever assigning (simulate SLA breach)
    from app.models.case import FraudCase
    from app.services import case_service

    case = db_session.get(FraudCase, case_id)
    case_service.system_escalate(db_session, case, breach_type="ack_overdue")
    db_session.commit()

    resp = client.post(f"/api/v1/cases/{case_id}/transition",
                        json={"to_status": "UNDER_INVESTIGATION", "note": "go"}, headers=sup_headers)
    assert resp.status_code == 409
    assert resp.json()["code"] == "NO_ASSIGNEE"


def test_alert_dismissal_releases_held_transaction(client, db_session, roles):
    make_account(db_session, account_number="2100000003")
    analyst = make_user(db_session, roles, "analyst", "an2@test.local")
    an_headers = auth_headers(client, "an2@test.local")

    # A medium-severity alert without hold (medium never holds); simulate by
    # inserting txn/prediction/alert directly since this test targets
    # dismiss-releases-a-HELD-transaction specifically (a high alert case).
    import uuid as uuid_module
    from decimal import Decimal

    from app.models.case import Alert
    from app.models.customer import Account
    from app.models.ml import ModelVersion, Prediction
    from app.models.transaction import Txn

    account = db_session.query(Account).filter(Account.account_number == "2100000003").one()
    model_version = ModelVersion(algorithm="xgboost", version="v-test-1", path="v-test-1", metrics={}, is_active=False)
    db_session.add(model_version)
    db_session.flush()

    txn = Txn(txn_ref="DISMISS-1", account_id=account.account_id, amount=Decimal("10000.00"), channel="NIP",
              txn_type="TRANSFER", txn_time=datetime.now(timezone.utc), beneficiary_account="123", location="Lagos",
              balance_before=Decimal("50000.00"), status="HELD")
    db_session.add(txn)
    db_session.flush()
    prediction = Prediction(txn_id=txn.txn_id, model_id=model_version.model_id, fraud_score=Decimal("0.75"),
                             risk_band="high", shap_values=[], features={}, latency_ms=Decimal("10.0"))
    db_session.add(prediction)
    db_session.flush()
    alert = Alert(prediction_id=prediction.prediction_id, severity="high", status="OPEN")
    db_session.add(alert)
    db_session.commit()

    resp = client.post(f"/api/v1/alerts/{alert.alert_id}/dismiss", json={"reason": "verified with customer"},
                        headers=an_headers)
    assert resp.status_code == 200, resp.text

    db_session.refresh(txn)
    assert txn.status == "APPROVED"
    db_session.refresh(alert)
    assert alert.status == "DISMISSED"
    assert alert.dismiss_reason == "verified with customer"
