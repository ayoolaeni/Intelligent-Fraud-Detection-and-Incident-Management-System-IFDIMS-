"""Auth schemas (Section 8.1)."""
from __future__ import annotations

import re
import uuid

from pydantic import BaseModel, field_validator

from app.core.security import validate_password_strength

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_email(v: str) -> str:
    if not _EMAIL_RE.match(v):
        raise ValueError("value is not a valid email address")
    return v


class LoginRequest(BaseModel):
    email: str
    password: str

    _check_email = field_validator("email")(_validate_email)


class UserOut(BaseModel):
    user_id: uuid.UUID
    full_name: str
    email: str
    role: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _check_strength(cls, v: str) -> str:
        validate_password_strength(v)
        return v
