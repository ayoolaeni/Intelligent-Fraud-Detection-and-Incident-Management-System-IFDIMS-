"""Case schemas (Section 8.4, 10)."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class CaseCreateRequest(BaseModel):
    source: str  # CUSTOMER_REPORT | MANUAL
    title: str
    description: str
    account_number: str | None = None
    txn_ref: str | None = None
    amount_at_risk: Decimal = Decimal("0")
    priority: str = "medium"


class CaseNoteOut(BaseModel):
    note_id: uuid.UUID
    user_id: uuid.UUID | None = None
    user_name: str | None = None
    note: str
    note_type: str
    created_at: datetime


class CaseAttachmentOut(BaseModel):
    attachment_id: uuid.UUID
    file_name: str
    content_type: str
    size_bytes: int
    uploaded_by: uuid.UUID | None = None
    created_at: datetime


class CaseOut(BaseModel):
    case_id: uuid.UUID
    case_number: str
    title: str
    source: str
    priority: str
    status: str
    outcome: str | None = None
    assigned_to: uuid.UUID | None = None
    assigned_to_name: str | None = None
    amount_at_risk: Decimal
    amount_recovered: Decimal
    opened_at: datetime
    ack_due_at: datetime
    resolve_due_at: datetime
    closed_at: datetime | None = None
    sla_state: str  # ok | due_soon | breached


class CaseDetailOut(BaseModel):
    case: CaseOut
    description: str
    alert_id: uuid.UUID | None = None
    txn_id: uuid.UUID | None = None
    account_number_masked: str | None = None
    fraud_type: str | None = None
    notes: list[CaseNoteOut] = []
    attachments: list[CaseAttachmentOut] = []
    allowed_transitions: list[str] = []
    can_assign: bool = False
    can_release_decline: bool = False


class AssignCaseRequest(BaseModel):
    user_id: uuid.UUID


class TransitionCaseRequest(BaseModel):
    to_status: str
    note: str
    outcome: str | None = None
    fraud_type: str | None = None
    amount_recovered: Decimal | None = None


class NoteCreateRequest(BaseModel):
    note: str
