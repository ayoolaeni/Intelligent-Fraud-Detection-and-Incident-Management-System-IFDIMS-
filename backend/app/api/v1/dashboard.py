"""Dashboard endpoints (Section 8.5)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.rbac import require_roles
from app.db import get_db
from app.models.case import Alert, FraudCase
from app.models.transaction import Txn
from app.models.user import AppUser
from app.schemas.dashboard import DashboardSummary, DashboardTrends, TrendPoint
from app.services import case_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

OPEN_CASE_STATUSES = ("NEW", "ASSIGNED", "UNDER_INVESTIGATION", "ESCALATED")


@router.get("/summary", response_model=DashboardSummary)
def summary(
    user: AppUser = Depends(require_roles("analyst", "supervisor", "admin")),
    db: Session = Depends(get_db),
) -> DashboardSummary:
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    window_30d = now - timedelta(days=30)

    open_alerts = {"medium": 0, "high": 0}
    for severity, count in db.execute(
        select(Alert.severity, func.count()).where(Alert.status == "OPEN").group_by(Alert.severity)
    ).all():
        open_alerts[severity] = count

    open_cases_by_priority = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for priority, count in db.execute(
        select(FraudCase.priority, func.count())
        .where(FraudCase.status.in_(OPEN_CASE_STATUSES))
        .group_by(FraudCase.priority)
    ).all():
        open_cases_by_priority[priority] = count

    open_cases = db.execute(select(FraudCase).where(FraudCase.status.in_(OPEN_CASE_STATUSES))).scalars().all()
    breaching = sum(1 for c in open_cases if case_service.sla_state(c, now) == "breached")
    due_soon = sum(1 for c in open_cases if case_service.sla_state(c, now) == "due_soon")

    transactions_today = db.execute(
        select(func.count()).select_from(Txn).where(Txn.created_at >= today_start)
    ).scalar_one()
    held_transactions = db.execute(
        select(func.count()).select_from(Txn).where(Txn.status == "HELD")
    ).scalar_one()

    resolved_30d = db.execute(
        select(FraudCase).where(FraudCase.resolved_at.is_not(None), FraudCase.resolved_at >= window_30d)
    ).scalars().all()
    confirmed = [c for c in resolved_30d if c.outcome == "confirmed_fraud"]
    false_positives = [c for c in resolved_30d if c.outcome == "false_positive"]
    confirmed_value = sum((c.amount_at_risk for c in confirmed), Decimal("0"))
    fp_rate = len(false_positives) / len(resolved_30d) if resolved_30d else 0.0
    avg_resolution_hours = (
        sum((c.resolved_at - c.opened_at).total_seconds() for c in resolved_30d) / len(resolved_30d) / 3600
        if resolved_30d else 0.0
    )

    return DashboardSummary(
        open_alerts=open_alerts,
        open_cases_by_priority=open_cases_by_priority,
        cases_breaching_sla=breaching,
        cases_due_soon=due_soon,
        transactions_today=transactions_today,
        held_transactions=held_transactions,
        confirmed_fraud_value_30d=confirmed_value,
        false_positive_rate_30d=round(fp_rate, 4),
        avg_resolution_hours_30d=round(avg_resolution_hours, 2),
    )


@router.get("/trends", response_model=DashboardTrends)
def trends(
    days: int = 30,
    user: AppUser = Depends(require_roles("analyst", "supervisor", "admin")),
    db: Session = Depends(get_db),
) -> DashboardTrends:
    from app.models.ml import Prediction

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)

    daily: list[TrendPoint] = []
    for i in range(days):
        day_start = (start + timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        txn_count = db.execute(
            select(func.count()).select_from(Txn).where(Txn.txn_time >= day_start, Txn.txn_time < day_end)
        ).scalar_one()
        alerts_medium = db.execute(
            select(func.count()).select_from(Alert).where(
                Alert.severity == "medium", Alert.created_at >= day_start, Alert.created_at < day_end
            )
        ).scalar_one()
        alerts_high = db.execute(
            select(func.count()).select_from(Alert).where(
                Alert.severity == "high", Alert.created_at >= day_start, Alert.created_at < day_end
            )
        ).scalar_one()
        cases_opened = db.execute(
            select(func.count()).select_from(FraudCase).where(
                FraudCase.opened_at >= day_start, FraudCase.opened_at < day_end
            )
        ).scalar_one()
        confirmed_today = db.execute(
            select(FraudCase).where(
                FraudCase.outcome == "confirmed_fraud", FraudCase.resolved_at >= day_start, FraudCase.resolved_at < day_end
            )
        ).scalars().all()

        daily.append(TrendPoint(
            date=day_start.date().isoformat(),
            transactions_scored=txn_count,
            alerts_medium=alerts_medium,
            alerts_high=alerts_high,
            cases_opened=cases_opened,
            confirmed_fraud_count=len(confirmed_today),
            confirmed_fraud_value=sum((c.amount_at_risk for c in confirmed_today), Decimal("0")),
        ))

    by_channel: dict[str, dict[str, int]] = {}
    for channel, severity, count in db.execute(
        select(Txn.channel, Alert.severity, func.count())
        .select_from(Alert)
        .join(Prediction, Prediction.prediction_id == Alert.prediction_id)
        .join(Txn, Txn.txn_id == Prediction.txn_id)
        .where(Alert.created_at >= start)
        .group_by(Txn.channel, Alert.severity)
    ).all():
        by_channel.setdefault(channel, {})[severity] = count

    top_fraud_types = [
        {"fraud_type": ft, "count": c}
        for ft, c in db.execute(
            select(FraudCase.fraud_type, func.count())
            .where(FraudCase.outcome == "confirmed_fraud", FraudCase.fraud_type.is_not(None), FraudCase.resolved_at >= start)
            .group_by(FraudCase.fraud_type)
            .order_by(func.count().desc())
        ).all()
    ]

    return DashboardTrends(daily=daily, by_channel=by_channel, top_fraud_types=top_fraud_types)
