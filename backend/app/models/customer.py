"""customer and account tables (Section 7.1)."""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import uuid_pk


class Customer(Base):
    __tablename__ = "customer"

    customer_id: Mapped[uuid.UUID] = uuid_pk("customer_id")
    bvn_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    phone_last4: Mapped[str] = mapped_column(String(4), nullable=False)
    date_joined: Mapped[date] = mapped_column(Date, nullable=False)
    risk_profile: Mapped[str] = mapped_column(String(10), nullable=False, default="low", server_default=text("'low'"))

    accounts: Mapped[list["Account"]] = relationship(back_populates="customer")


class Account(Base):
    __tablename__ = "account"

    account_id: Mapped[uuid.UUID] = uuid_pk("account_id")
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customer.customer_id"), nullable=False)
    account_number: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    account_type: Mapped[str] = mapped_column(String(10), nullable=False)
    opened_on: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="ACTIVE", server_default=text("'ACTIVE'"))

    customer: Mapped[Customer] = relationship(back_populates="accounts")
