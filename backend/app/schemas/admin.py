"""Admin schemas (Section 8.8)."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator

from app.core.security import validate_password_strength
from app.schemas.auth import _validate_email


class UserCreateRequest(BaseModel):
    full_name: str
    email: str
    role: str
    temporary_password: str

    _check_email = field_validator("email")(_validate_email)

    @field_validator("temporary_password")
    @classmethod
    def _check_strength(cls, v: str) -> str:
        validate_password_strength(v)
        return v


class UserUpdateRequest(BaseModel):
    full_name: str | None = None
    role: str | None = None
    is_active: bool | None = None


class UserOut(BaseModel):
    user_id: uuid.UUID
    full_name: str
    email: str
    role: str
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None = None


class ResetPasswordResponse(BaseModel):
    temporary_password: str


class SlaSetting(BaseModel):
    ack_minutes: int
    resolve_minutes: int


class SettingsOut(BaseModel):
    risk_threshold_medium: float
    risk_threshold_high: float
    critical_amount_ngn: float
    sla: dict[str, SlaSetting]
    auto_assign: bool
    hold_high_risk: bool


class SettingsUpdate(BaseModel):
    risk_threshold_medium: float | None = None
    risk_threshold_high: float | None = None
    critical_amount_ngn: float | None = None
    sla: dict[str, SlaSetting] | None = None
    auto_assign: bool | None = None
    hold_high_risk: bool | None = None


class ModelVersionOut(BaseModel):
    model_id: uuid.UUID
    algorithm: str
    version: str
    metrics: dict
    deployed_on: datetime | None = None
    is_active: bool


class AuditLogOut(BaseModel):
    log_id: uuid.UUID
    user_id: uuid.UUID | None = None
    actor: str
    action: str
    entity: str
    entity_id: str
    details: dict
    ip_address: str | None = None
    timestamp: datetime
