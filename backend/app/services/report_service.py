"""CSV/PDF reports (Section 8.6, FR11)."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.case import Alert, FraudCase
from app.models.customer import Account
from app.models.ml import ModelVersion, Prediction
from app.models.transaction import Txn
from app.models.user import AppUser


def _apply_common_filters(query, model, from_dt, to_dt, date_field):
    if from_dt:
        query = query.where(date_field >= from_dt)
    if to_dt:
        query = query.where(date_field <= to_dt)
    return query


def rows_to_csv(rows: list[dict], fieldnames: list[str]) -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode("utf-8")


def cases_report_rows(db: Session, from_dt, to_dt, channel: str | None) -> list[dict]:
    query = select(FraudCase, Txn, AppUser).outerjoin(Txn, Txn.txn_id == FraudCase.txn_id).outerjoin(
        AppUser, AppUser.user_id == FraudCase.assigned_to
    )
    query = _apply_common_filters(query, FraudCase, from_dt, to_dt, FraudCase.opened_at)
    if channel:
        query = query.where(Txn.channel == channel)
    rows = []
    for case, txn, assignee in db.execute(query).all():
        ack_hours = (
            (case.acknowledged_at - case.opened_at).total_seconds() / 3600 if case.acknowledged_at else None
        )
        resolve_hours = (
            (case.resolved_at - case.opened_at).total_seconds() / 3600 if case.resolved_at else None
        )
        sla_met = None
        if case.resolved_at:
            sla_met = case.resolved_at <= case.resolve_due_at
        rows.append({
            "case_number": case.case_number,
            "opened_at": case.opened_at.isoformat(),
            "closed_at": case.closed_at.isoformat() if case.closed_at else "",
            "priority": case.priority,
            "status": case.status,
            "outcome": case.outcome or "",
            "fraud_type": case.fraud_type or "",
            "amount_at_risk": str(case.amount_at_risk),
            "amount_recovered": str(case.amount_recovered),
            "assigned_analyst": assignee.full_name if assignee else "",
            "hours_to_acknowledge": f"{ack_hours:.2f}" if ack_hours is not None else "",
            "hours_to_resolve": f"{resolve_hours:.2f}" if resolve_hours is not None else "",
            "sla_met": "" if sla_met is None else ("yes" if sla_met else "no"),
        })
    return rows


def alerts_report_rows(db: Session, from_dt, to_dt, channel: str | None) -> list[dict]:
    query = select(Alert, Prediction, Txn).join(Prediction, Prediction.prediction_id == Alert.prediction_id).join(
        Txn, Txn.txn_id == Prediction.txn_id
    )
    query = _apply_common_filters(query, Alert, from_dt, to_dt, Alert.created_at)
    if channel:
        query = query.where(Txn.channel == channel)
    rows = []
    for alert, prediction, txn in db.execute(query).all():
        handling_hours = (
            (alert.reviewed_at - alert.created_at).total_seconds() / 3600 if alert.reviewed_at else None
        )
        rows.append({
            "alert_id": str(alert.alert_id),
            "created_at": alert.created_at.isoformat(),
            "channel": txn.channel,
            "fraud_score": str(prediction.fraud_score),
            "risk_band": prediction.risk_band,
            "severity": alert.severity,
            "status": alert.status,
            "outcome": "dismissed" if alert.status == "DISMISSED" else ("case_opened" if alert.status == "CASE_OPENED" else ""),
            "handling_hours": f"{handling_hours:.2f}" if handling_hours is not None else "",
        })
    return rows


def fraud_summary(db: Session, from_dt, to_dt, channel: str | None) -> dict:
    cases = cases_report_rows(db, from_dt, to_dt, channel)
    alerts = alerts_report_rows(db, from_dt, to_dt, channel)

    confirmed = [c for c in cases if c["outcome"] == "confirmed_fraud"]
    false_positives = [c for c in cases if c["outcome"] == "false_positive"]
    resolved = confirmed + false_positives

    by_channel: dict[str, int] = {}
    by_fraud_type: dict[str, int] = {}
    for row in db.execute(
        select(Txn.channel, FraudCase.fraud_type)
        .join(FraudCase, FraudCase.txn_id == Txn.txn_id)
        .where(FraudCase.outcome == "confirmed_fraud")
    ).all():
        by_channel[row[0]] = by_channel.get(row[0], 0) + 1
        if row[1]:
            by_fraud_type[row[1]] = by_fraud_type.get(row[1], 0) + 1

    confirmed_value = sum(float(c["amount_at_risk"]) for c in confirmed)
    recovered_value = sum(float(c["amount_recovered"]) for c in confirmed)
    sla_met_count = sum(1 for c in cases if c["sla_met"] == "yes")
    sla_total = sum(1 for c in cases if c["sla_met"] in ("yes", "no"))
    fp_rate = len(false_positives) / len(resolved) if resolved else 0.0

    active_model = db.execute(select(ModelVersion).where(ModelVersion.is_active.is_(True))).scalar_one_or_none()

    return {
        "total_confirmed_fraud_cases": len(confirmed),
        "total_false_positives": len(false_positives),
        "confirmed_fraud_value": confirmed_value,
        "recovered_value": recovered_value,
        "false_positive_rate": fp_rate,
        "sla_compliance_pct": (sla_met_count / sla_total * 100) if sla_total else None,
        "by_channel": by_channel,
        "by_fraud_type": by_fraud_type,
        "total_alerts": len(alerts),
        "active_model_version": active_model.version if active_model else None,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def nibss_incidents_rows(db: Session, from_dt, to_dt, channel: str | None) -> list[dict]:
    query = (
        select(FraudCase, Txn, Account)
        .join(Txn, Txn.txn_id == FraudCase.txn_id)
        .join(Account, Account.account_id == Txn.account_id)
        .where(FraudCase.outcome == "confirmed_fraud")
    )
    query = _apply_common_filters(query, FraudCase, from_dt, to_dt, FraudCase.opened_at)
    if channel:
        query = query.where(Txn.channel == channel)
    rows = []
    for case, txn, account in db.execute(query).all():
        rows.append({
            "case_number": case.case_number,
            "date": case.opened_at.date().isoformat(),
            "channel": txn.channel,
            "fraud_type": case.fraud_type or "",
            "amount": str(case.amount_at_risk),
            "amount_recovered": str(case.amount_recovered),
            "account_type": account.account_type,
            "customer_state": txn.location,
            "status": case.status,
        })
    return rows


def fraud_summary_pdf(summary: dict, generated_by: str) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("IFDIMS Fraud Summary Report", styles["Title"]))
    elements.append(Paragraph(f"Generated at {summary['generated_at']} by {generated_by}", styles["Normal"]))
    elements.append(Spacer(1, 1 * cm))

    table_data = [
        ["Metric", "Value"],
        ["Confirmed fraud cases", str(summary["total_confirmed_fraud_cases"])],
        ["False positives", str(summary["total_false_positives"])],
        ["Confirmed fraud value", f"₦{summary['confirmed_fraud_value']:,.2f}"],
        ["Recovered value", f"₦{summary['recovered_value']:,.2f}"],
        ["False positive rate", f"{summary['false_positive_rate']:.1%}"],
        ["SLA compliance", f"{summary['sla_compliance_pct']:.1f}%" if summary["sla_compliance_pct"] is not None else "n/a"],
        ["Active model version", summary["active_model_version"] or "none"],
    ]
    table = Table(table_data, colWidths=[8 * cm, 8 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 1 * cm))

    if summary["by_channel"]:
        fig, ax = plt.subplots(figsize=(6, 3.5))
        channels = list(summary["by_channel"].keys())
        values = list(summary["by_channel"].values())
        ax.bar(channels, values, color="#2563eb")
        ax.set_title("Confirmed fraud by channel")
        ax.set_ylabel("Cases")
        fig.tight_layout()
        img_buf = io.BytesIO()
        fig.savefig(img_buf, format="png", dpi=150)
        plt.close(fig)
        img_buf.seek(0)
        elements.append(Image(img_buf, width=16 * cm, height=9.3 * cm))

    doc.build(elements)
    return buf.getvalue()
