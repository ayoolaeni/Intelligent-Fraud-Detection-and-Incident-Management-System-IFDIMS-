"""Transaction scoring and read schemas (Section 8.2, 4.2)."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, field_validator

from fraud_core.constants import CHANNELS, SECURITY_EVENT_TYPES, TXN_TYPES


class ScoreTransactionRequest(BaseModel):
    txn_ref: str
    account_number: str
    amount: Decimal
    channel: str
    txn_type: str
    txn_time: datetime
    beneficiary_account: str | None = None
    beneficiary_bank: str | None = None
    device_id: str | None = None
    location: str
    balance_before: Decimal

    @field_validator("amount")
    @classmethod
    def _amount_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("amount must be greater than 0")
        return v

    @field_validator("channel")
    @classmethod
    def _channel_valid(cls, v: str) -> str:
        if v not in CHANNELS:
            raise ValueError(f"channel must be one of {CHANNELS}")
        return v

    @field_validator("txn_type")
    @classmethod
    def _txn_type_valid(cls, v: str) -> str:
        if v not in TXN_TYPES:
            raise ValueError(f"txn_type must be one of {TXN_TYPES}")
        return v


class TopFactor(BaseModel):
    feature: str
    label: str
    raw_value: float | int | str
    contribution: float
    description: str


class ScoreTransactionResponse(BaseModel):
    txn_id: uuid.UUID
    prediction_id: uuid.UUID
    fraud_score: float
    risk_band: str
    decision: str
    alert_id: uuid.UUID | None = None
    case_id: uuid.UUID | None = None
    case_number: str | None = None
    top_factors: list[TopFactor]
    model_version: str
    latency_ms: float


class SecurityEventRequest(BaseModel):
    account_number: str
    event_type: str
    event_time: datetime

    @field_validator("event_type")
    @classmethod
    def _event_type_valid(cls, v: str) -> str:
        if v not in SECURITY_EVENT_TYPES:
            raise ValueError(f"event_type must be one of {SECURITY_EVENT_TYPES}")
        return v


class CustomerSummary(BaseModel):
    customer_id: uuid.UUID
    full_name: str
    phone_masked: str
    risk_profile: str
    account_age_days: float


class TransactionOut(BaseModel):
    txn_id: uuid.UUID
    txn_ref: str
    account_number_masked: str
    amount: Decimal
    channel: str
    txn_type: str
    txn_time: datetime
    location: str
    status: str
    fraud_score: float | None = None
    risk_band: str | None = None


class TransactionDetailOut(BaseModel):
    txn: TransactionOut
    prediction: dict | None = None
    alert_id: uuid.UUID | None = None
    case_id: uuid.UUID | None = None
    case_number: str | None = None
    customer: CustomerSummary | None = None
    recent_transactions: list[TransactionOut] = []


class ReleaseDeclineRequest(BaseModel):
    reason: str
