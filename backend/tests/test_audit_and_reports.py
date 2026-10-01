"""Audit log cannot be updated or deleted (Section 15.3); reports return
valid CSV/PDF (Section 8.6).
"""
from __future__ import annotations

import csv
import io

import pytest
from sqlalchemy.exc import ProgrammingError

from tests.conftest import auth_headers, make_user


def test_audit_log_cannot_be_updated(db_session):
    from app.models.audit import AuditLog

    log = AuditLog(actor="system", action="TEST", entity="role", entity_id="x", details={})
    db_session.add(log)
    db_session.commit()

    log.action = "HACKED"
    with pytest.raises(ProgrammingError):
        db_session.commit()
    db_session.rollback()


def test_audit_log_cannot_be_deleted(db_session):
    from app.models.audit import AuditLog

    log = AuditLog(actor="system", action="TEST2", entity="role", entity_id="y", details={})
    db_session.add(log)
    db_session.commit()

    db_session.delete(log)
    with pytest.raises(ProgrammingError):
        db_session.commit()
    db_session.rollback()


def test_reports_cases_csv_valid(client, db_session, roles):
    make_user(db_session, roles, "supervisor", "repsup@test.local")
    headers = auth_headers(client, "repsup@test.local")
    resp = client.get("/api/v1/reports/cases", headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    reader = csv.reader(io.StringIO(resp.text))
    header = next(reader)
    assert "case_number" in header
    assert "sla_met" in header


def test_reports_fraud_summary_pdf_valid(client, db_session, roles):
    make_user(db_session, roles, "supervisor", "reppdf@test.local")
    headers = auth_headers(client, "reppdf@test.local")
    resp = client.get("/api/v1/reports/fraud-summary?format=pdf", headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")


def test_reports_forbidden_for_analyst(client, db_session, roles):
    make_user(db_session, roles, "analyst", "repan@test.local")
    headers = auth_headers(client, "repan@test.local")
    resp = client.get("/api/v1/reports/cases", headers=headers)
    assert resp.status_code == 403
