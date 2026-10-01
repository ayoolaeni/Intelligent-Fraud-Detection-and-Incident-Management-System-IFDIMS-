"""txn table (Section 7.1; table name 'txn' since 'transaction' is reserved-ish)."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import uuid_pk


class Txn(Base):
    __tablename__ = "txn"
    __table_args__ = (
        Index("ix_txn_account_time", "account_id", "txn_time"),
        Index("ix_txn_account_device", "account_id", "device_id"),
        Index("ix_txn_account_beneficiary", "account_id", "beneficiary_account"),
        Index("ix_txn_created_at", "created_at"),
        Index("ix_txn_status", "status"),
    )

    txn_id: Mapped[uuid.UUID] = uuid_pk("txn_id")
    txn_ref: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("account.account_id"), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    txn_type: Mapped[str] = mapped_column(String(20), nullable=False)
    txn_time: Mapped[datetime] = mapped_column(nullable=False)
    beneficiary_account: Mapped[str | None] = mapped_column(String(20), nullable=True)
    beneficiary_bank: Mapped[str | None] = mapped_column(String(10), nullable=True)
    device_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    location: Mapped[str] = mapped_column(String(100), nullable=False)
    balance_before: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="APPROVED")
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))

    account: Mapped["Account"] = relationship()
    prediction: Mapped["Prediction | None"] = relationship(back_populates="txn", uselist=False)
