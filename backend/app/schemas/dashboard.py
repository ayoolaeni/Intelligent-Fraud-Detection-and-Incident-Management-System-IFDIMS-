"""Dashboard schemas (Section 8.5)."""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class DashboardSummary(BaseModel):
    open_alerts: dict[str, int]
    open_cases_by_priority: dict[str, int]
    cases_breaching_sla: int
    cases_due_soon: int
    transactions_today: int
    held_transactions: int
    confirmed_fraud_value_30d: Decimal
    false_positive_rate_30d: float
    avg_resolution_hours_30d: float


class TrendPoint(BaseModel):
    date: str
    transactions_scored: int
    alerts_medium: int
    alerts_high: int
    cases_opened: int
    confirmed_fraud_count: int
    confirmed_fraud_value: Decimal


class DashboardTrends(BaseModel):
    daily: list[TrendPoint]
    by_channel: dict[str, dict[str, int]]
    top_fraud_types: list[dict]
