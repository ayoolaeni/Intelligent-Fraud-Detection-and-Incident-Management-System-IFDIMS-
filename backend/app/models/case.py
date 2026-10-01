"""alert, fraud_case, case_note, case_attachment tables (Section 7.1)."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import uuid_pk


class Alert(Base):
    __tablename__ = "alert"
    __table_args__ = (
        Index("ix_alert_status_created", "status", "created_at"),
    )

    alert_id: Mapped[uuid.UUID] = uuid_pk("alert_id")
    prediction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prediction.prediction_id"), unique=True, nullable=False
    )
    severity: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="OPEN")
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("app_user.user_id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    dismiss_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))

    prediction: Mapped["Prediction"] = relationship()


class FraudCase(Base):
    __tablename__ = "fraud_case"
    __table_args__ = (
        Index("ix_fraud_case_status_priority", "status", "priority"),
        Index("ix_fraud_case_assigned_status", "assigned_to", "status"),
        Index("ix_fraud_case_resolve_due", "resolve_due_at"),
    )

    case_id: Mapped[uuid.UUID] = uuid_pk("case_id")
    case_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    alert_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("alert.alert_id"), nullable=True)
    txn_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("txn.txn_id"), nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("app_user.user_id"), nullable=True)
    priority: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(25), nullable=False, default="NEW")
    outcome: Mapped[str | None] = mapped_column(String(25), nullable=True)
    fraud_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    amount_at_risk: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False, default=0)
    amount_recovered: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False, default=0, server_default=text("0"))
    ack_due_at: Mapped[datetime] = mapped_column(nullable=False)
    resolve_due_at: Mapped[datetime] = mapped_column(nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(nullable=True)
    opened_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    closed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("app_user.user_id"), nullable=True)

    notes: Mapped[list["CaseNote"]] = relationship(back_populates="case", order_by="CaseNote.created_at")
    attachments: Mapped[list["CaseAttachment"]] = relationship(back_populates="case")
    alert: Mapped[Alert | None] = relationship()
    txn: Mapped["Txn | None"] = relationship()


class CaseNote(Base):
    __tablename__ = "case_note"

    note_id: Mapped[uuid.UUID] = uuid_pk("note_id")
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("fraud_case.case_id"), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("app_user.user_id"), nullable=True)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    note_type: Mapped[str] = mapped_column(String(20), nullable=False, default="NOTE")
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))

    case: Mapped[FraudCase] = relationship(back_populates="notes")


class CaseAttachment(Base):
    __tablename__ = "case_attachment"

    attachment_id: Mapped[uuid.UUID] = uuid_pk("attachment_id")
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("fraud_case.case_id"), nullable=False)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("app_user.user_id"), nullable=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))

    case: Mapped[FraudCase] = relationship(back_populates="attachments")
