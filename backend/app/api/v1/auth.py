"""Authentication endpoints (Section 8.1)."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.errors import ApiError
from app.core.rate_limit import login_rate_limiter
from app.core.rbac import get_current_user
from app.core.security import (
    create_access_token,
    hash_password,
    login_throttle,
    verify_password,
)
from app.db import get_db
from app.models.user import AppUser
from app.schemas.auth import ChangePasswordRequest, LoginRequest, LoginResponse, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> LoginResponse:
    login_rate_limiter.check(request.client.host if request.client else "unknown")

    if login_throttle.is_locked(payload.email):
        wait = login_throttle.seconds_until_unlock(payload.email)
        raise ApiError(423, "ACCOUNT_LOCKED", f"Too many failed attempts; try again in {wait} seconds")

    user = db.query(AppUser).filter(AppUser.email == payload.email).one_or_none()
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        login_throttle.record_failure(payload.email)
        audit(db, action="LOGIN_FAILED", entity="app_user", entity_id=payload.email, actor=payload.email,
              ip_address=request.client.host if request.client else None)
        db.commit()
        raise ApiError(401, "INVALID_CREDENTIALS", "Invalid email or password")

    login_throttle.reset(payload.email)
    user.last_login_at = datetime.now(timezone.utc)
    token, expires_in = create_access_token(str(user.user_id), user.role_name)
    audit(db, action="LOGIN", entity="app_user", entity_id=str(user.user_id), user=user,
          ip_address=request.client.host if request.client else None)
    db.commit()

    return LoginResponse(
        access_token=token,
        expires_in=expires_in,
        user=UserOut(user_id=user.user_id, full_name=user.full_name, email=user.email, role=user.role_name),
    )


@router.get("/me", response_model=UserOut)
def me(user: AppUser = Depends(get_current_user)) -> UserOut:
    return UserOut(user_id=user.user_id, full_name=user.full_name, email=user.email, role=user.role_name)


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if not verify_password(payload.current_password, user.password_hash):
        raise ApiError(401, "INVALID_CREDENTIALS", "Current password is incorrect")
    # payload.new_password already passed validate_password_strength as a
    # Pydantic field_validator on ChangePasswordRequest.
    user.password_hash = hash_password(payload.new_password)
    audit(db, action="PASSWORD_CHANGED", entity="app_user", entity_id=str(user.user_id), user=user)
    db.commit()
    return {"detail": "Password changed"}
