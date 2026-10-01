"""Coverage for read-heavy endpoints (alerts/cases/transactions/dashboard/
notifications listing and detail views) and the SLA scheduler, which the
happier-path tests elsewhere don't exercise directly.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tests.conftest import auth_headers, make_account, make_user

API_KEY_HEADERS = {"X-API-Key": "test-api-key"}


def _score(client, account_number: str, txn_ref: str, amount: str = "1000.00"):
    payload = {
        "txn_ref": txn_ref, "account_number": account_number, "amount": amount, "channel": "NIP",
        "txn_type": "TRANSFER", "txn_time": datetime.now(timezone.utc).isoformat(),
        "beneficiary_account": "9990001111", "beneficiary_bank": "058", "device_id": "dev-1",
        "location": "Lagos", "balance_before": "500000.00",
    }
    return client.post("/api/v1/transactions/score", json=payload, headers=API_KEY_HEADERS)


def test_alert_list_and_detail(client, db_session, roles, active_model):
    make_account(db_session, account_number="2300000001")
    make_user(db_session, roles, "analyst", "readan1@test.local")
    headers = auth_headers(client, "readan1@test.local")

    score = _score(client, "2300000001", "READ-ALERT-1", amount="480000.00")
    assert score.status_code == 200
    body = score.json()
    assert body["risk_band"] == "high"
    alert_id = body["alert_id"]

    resp = client.get("/api/v1/alerts", params={"status": "OPEN"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1

    resp = client.get("/api/v1/alerts", params={"severity": "high", "sort": "fraud_score"}, headers=headers)
    assert resp.status_code == 200

    detail = client.get(f"/api/v1/alerts/{alert_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["alert"]["alert_id"] == alert_id
    assert len(detail.json()["top_factors"]) > 0

    resp = client.get("/api/v1/alerts/00000000-0000-0000-0000-000000000000", headers=headers)
    assert resp.status_code == 404


def test_high_alert_with_auto_case_can_still_be_dismissed(client, db_session, roles, active_model):
    """Regression test for docs/DECISIONS.md D20: an auto-created high-risk
    case's alert must stay OPEN, not CASE_OPENED, so it can still be
    dismissed (releasing the held transaction) as a fast path for false
    positives.
    """
    make_account(db_session, account_number="2300000008")
    make_user(db_session, roles, "analyst", "readan8@test.local")
    headers = auth_headers(client, "readan8@test.local")

    score = _score(client, "2300000008", "READ-DISMISS-HIGH-1", amount="480000.00")
    body = score.json()
    assert body["risk_band"] == "high"
    assert body["case_id"] is not None

    resp = client.post(f"/api/v1/alerts/{body['alert_id']}/dismiss", json={"reason": "confirmed legitimate"}, headers=headers)
    assert resp.status_code == 200, resp.text

    from app.models.transaction import Txn

    txn = db_session.query(Txn).filter(Txn.txn_ref == "READ-DISMISS-HIGH-1").one()
    assert txn.status == "APPROVED"


def test_case_list_filters_and_search(client, db_session, roles, active_model):
    make_account(db_session, account_number="2300000002")
    analyst = make_user(db_session, roles, "analyst", "readan2@test.local")
    supervisor = make_user(db_session, roles, "supervisor", "readsup2@test.local")
    an_headers = auth_headers(client, "readan2@test.local")
    sup_headers = auth_headers(client, "readsup2@test.local")

    score = _score(client, "2300000002", "READ-CASE-1", amount="480000.00")
    case_id = score.json()["case_id"]

    resp = client.get("/api/v1/cases", params={"status": "NEW"}, headers=an_headers)
    assert resp.status_code == 200
    assert any(c["case_id"] == case_id for c in resp.json()["items"])

    resp = client.get("/api/v1/cases", params={"assigned_to": "me"}, headers=an_headers)
    assert resp.status_code == 200

    resp = client.get("/api/v1/cases", params={"q": "READ-CASE"}, headers=sup_headers)
    assert resp.status_code == 200

    resp = client.get("/api/v1/cases", params={"priority": "high", "source": "ALERT"}, headers=sup_headers)
    assert resp.status_code == 200

    resp = client.get("/api/v1/cases", params={"overdue": True}, headers=sup_headers)
    assert resp.status_code == 200

    resp = client.get("/api/v1/cases/meta/assignable-users", headers=sup_headers)
    assert resp.status_code == 200
    assert resp.status_code != 403

    resp = client.get("/api/v1/cases/meta/assignable-users", headers=an_headers)
    assert resp.status_code == 403


def test_transaction_list_and_detail(client, db_session, roles, active_model):
    make_account(db_session, account_number="2300000003")
    make_user(db_session, roles, "supervisor", "readsup3@test.local")
    headers = auth_headers(client, "readsup3@test.local")

    score = _score(client, "2300000003", "READ-TXN-1")
    txn_id = score.json()["txn_id"]

    resp = client.get("/api/v1/transactions", params={"account_number": "2300000003"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1

    resp = client.get("/api/v1/transactions", params={"channel": "NIP", "min_amount": 1}, headers=headers)
    assert resp.status_code == 200

    detail = client.get(f"/api/v1/transactions/{txn_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["txn"]["txn_id"] == txn_id
    assert detail.json()["customer"] is not None

    resp = client.get("/api/v1/transactions/00000000-0000-0000-0000-000000000000", headers=headers)
    assert resp.status_code == 404


def test_dashboard_summary_and_trends(client, db_session, roles, active_model):
    make_account(db_session, account_number="2300000004")
    make_user(db_session, roles, "supervisor", "readsup4@test.local")
    headers = auth_headers(client, "readsup4@test.local")

    _score(client, "2300000004", "READ-DASH-1", amount="480000.00")

    resp = client.get("/api/v1/dashboard/summary", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["open_alerts"]["high"] >= 1
    assert body["held_transactions"] >= 1

    resp = client.get("/api/v1/dashboard/trends", params={"days": 7}, headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()["daily"]) == 7


def test_notifications_list_and_mark_read(client, db_session, roles, active_model):
    make_account(db_session, account_number="2300000005")
    analyst = make_user(db_session, roles, "analyst", "readan5@test.local")
    headers = auth_headers(client, "readan5@test.local")

    _score(client, "2300000005", "READ-NOTIF-1", amount="480000.00")

    resp = client.get("/api/v1/notifications", headers=headers)
    assert resp.status_code == 200

    resp = client.post("/api/v1/notifications/read-all", headers=headers)
    assert resp.status_code == 200

    resp = client.get("/api/v1/notifications", params={"unread": True}, headers=headers)
    assert resp.status_code == 200
    assert all(n["is_read"] for n in resp.json()) or resp.json() == []


def test_sla_scheduler_escalates_overdue_case(client, db_session, roles, active_model):
    make_account(db_session, account_number="2300000006")
    make_user(db_session, roles, "supervisor", "readsup6@test.local")

    score = _score(client, "2300000006", "READ-SLA-1", amount="480000.00")
    case_id = score.json()["case_id"]

    from app.models.case import FraudCase

    case = db_session.get(FraudCase, case_id)
    case.ack_due_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()

    from app.services import sla_service

    sla_service._check_breaches(db_session)
    db_session.commit()

    db_session.refresh(case)
    assert case.status == "ESCALATED"


def test_reports_alerts_csv(client, db_session, roles, active_model):
    make_account(db_session, account_number="2300000007")
    make_user(db_session, roles, "supervisor", "readsup7@test.local")
    headers = auth_headers(client, "readsup7@test.local")

    _score(client, "2300000007", "READ-REPORT-1", amount="480000.00")

    resp = client.get("/api/v1/reports/alerts", headers=headers)
    assert resp.status_code == 200
    assert "alert_id" in resp.text

    resp = client.get("/api/v1/reports/nibss-incidents", headers=headers)
    assert resp.status_code == 200
