"""Alert schemas (Section 8.3)."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.schemas.transaction import CustomerSummary, TopFactor, TransactionOut


class AlertOut(BaseModel):
    alert_id: uuid.UUID
    txn_id: uuid.UUID
    account_number_masked: str
    channel: str
    amount: Decimal
    fraud_score: float
    risk_band: str
    severity: str
    status: str
    created_at: datetime
    case_id: uuid.UUID | None = None


class AlertDetailOut(BaseModel):
    alert: AlertOut
    txn: TransactionOut
    top_factors: list[TopFactor]
    customer: CustomerSummary | None = None
    recent_transactions: list[TransactionOut] = []


class DismissAlertRequest(BaseModel):
    reason: str
