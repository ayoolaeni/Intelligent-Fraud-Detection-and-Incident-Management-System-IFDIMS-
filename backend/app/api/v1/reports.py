"""Report endpoints (Section 8.6, FR11)."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.rbac import require_roles
from app.db import get_db
from app.models.user import AppUser
from app.services import report_service

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/cases")
def cases_report(
    from_: datetime | None = None,
    to: datetime | None = None,
    channel: str | None = None,
    format: str = "csv",
    user: AppUser = Depends(require_roles("supervisor", "admin")),
    db: Session = Depends(get_db),
) -> Response:
    rows = report_service.cases_report_rows(db, from_, to, channel)
    fieldnames = [
        "case_number", "opened_at", "closed_at", "priority", "status", "outcome", "fraud_type",
        "amount_at_risk", "amount_recovered", "assigned_analyst", "hours_to_acknowledge",
        "hours_to_resolve", "sla_met",
    ]
    if format == "csv":
        csv_bytes = report_service.rows_to_csv(rows, fieldnames)
        return Response(csv_bytes, media_type="text/csv",
                         headers={"Content-Disposition": "attachment; filename=cases_report.csv"})
    raise ApiError(400, "UNSUPPORTED_FORMAT", "Only format=csv is supported for this report")


@router.get("/alerts")
def alerts_report(
    from_: datetime | None = None,
    to: datetime | None = None,
    channel: str | None = None,
    format: str = "csv",
    user: AppUser = Depends(require_roles("supervisor", "admin")),
    db: Session = Depends(get_db),
) -> Response:
    rows = report_service.alerts_report_rows(db, from_, to, channel)
    fieldnames = ["alert_id", "created_at", "channel", "fraud_score", "risk_band", "severity", "status",
                  "outcome", "handling_hours"]
    if format == "csv":
        csv_bytes = report_service.rows_to_csv(rows, fieldnames)
        return Response(csv_bytes, media_type="text/csv",
                         headers={"Content-Disposition": "attachment; filename=alerts_report.csv"})
    raise ApiError(400, "UNSUPPORTED_FORMAT", "Only format=csv is supported for this report")


@router.get("/fraud-summary")
def fraud_summary_report(
    from_: datetime | None = None,
    to: datetime | None = None,
    channel: str | None = None,
    format: str = "csv",
    user: AppUser = Depends(require_roles("supervisor", "admin")),
    db: Session = Depends(get_db),
) -> Response:
    summary = report_service.fraud_summary(db, from_, to, channel)
    if format == "pdf":
        pdf_bytes = report_service.fraud_summary_pdf(summary, generated_by=user.email)
        return Response(pdf_bytes, media_type="application/pdf",
                         headers={"Content-Disposition": "attachment; filename=fraud_summary.pdf"})
    fieldnames = list(summary.keys())
    flat = {k: (v if not isinstance(v, dict) else str(v)) for k, v in summary.items()}
    csv_bytes = report_service.rows_to_csv([flat], fieldnames)
    return Response(csv_bytes, media_type="text/csv",
                     headers={"Content-Disposition": "attachment; filename=fraud_summary.csv"})


@router.get("/nibss-incidents")
def nibss_incidents_report(
    from_: datetime | None = None,
    to: datetime | None = None,
    channel: str | None = None,
    format: str = "csv",
    user: AppUser = Depends(require_roles("supervisor", "admin")),
    db: Session = Depends(get_db),
) -> Response:
    rows = report_service.nibss_incidents_rows(db, from_, to, channel)
    fieldnames = ["case_number", "date", "channel", "fraud_type", "amount", "amount_recovered",
                  "account_type", "customer_state", "status"]
    csv_bytes = report_service.rows_to_csv(rows, fieldnames)
    return Response(csv_bytes, media_type="text/csv",
                     headers={"Content-Disposition": "attachment; filename=nibss_incidents.csv"})
