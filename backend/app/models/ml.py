"""model_version and prediction tables (Section 7.1)."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, Numeric, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import uuid_pk


class ModelVersion(Base):
    __tablename__ = "model_version"

    model_id: Mapped[uuid.UUID] = uuid_pk("model_id")
    algorithm: Mapped[str] = mapped_column(String(30), nullable=False)
    version: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    path: Mapped[str] = mapped_column(String(255), nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    deployed_on: Mapped[datetime | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))


class Prediction(Base):
    __tablename__ = "prediction"
    __table_args__ = (
        Index("ix_prediction_band_created", "risk_band", "created_at"),
    )

    prediction_id: Mapped[uuid.UUID] = uuid_pk("prediction_id")
    txn_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("txn.txn_id"), unique=True, nullable=False)
    model_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("model_version.model_id"), nullable=False)
    fraud_score: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    risk_band: Mapped[str] = mapped_column(String(10), nullable=False)
    shap_values: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    features: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    latency_ms: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))

    txn: Mapped["Txn"] = relationship(back_populates="prediction")
    model_version: Mapped[ModelVersion] = relationship()
