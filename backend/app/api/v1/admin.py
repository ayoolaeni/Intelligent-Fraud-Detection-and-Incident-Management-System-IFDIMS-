"""Administration endpoints (Section 8.8, FR13)."""
from __future__ import annotations

import io
import secrets
import string
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.errors import ApiError
from app.core.rbac import require_roles
from app.core.security import hash_password
from app.db import get_db
from app.models.case import CaseNote, FraudCase
from app.models.ml import ModelVersion
from app.models.transaction import Txn
from app.models.user import AppUser, Role
from app.schemas.admin import (
    AuditLogOut,
    ModelVersionOut,
    ResetPasswordResponse,
    SettingsOut,
    SettingsUpdate,
    UserCreateRequest,
    UserOut,
    UserUpdateRequest,
)
from app.schemas.common import Page
from app.services.model_registry import model_registry
from app.services.settings_service import get_settings_dict, update_settings

router = APIRouter(prefix="/admin", tags=["admin"])


def _random_password(length: int = 14) -> str:
    alphabet = string.ascii_letters + string.digits
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(length))
        if any(c.isalpha() for c in pw) and any(c.isdigit() for c in pw):
            return pw


@router.get("/users", response_model=Page[UserOut])
def list_users(
    page: int = 1,
    page_size: int = 25,
    admin: AppUser = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> Page[UserOut]:
    page_size = min(page_size, 100)
    total = db.query(AppUser).count()
    rows = db.execute(
        select(AppUser).order_by(AppUser.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()
    items = [UserOut(user_id=u.user_id, full_name=u.full_name, email=u.email, role=u.role_name,
                      is_active=u.is_active, created_at=u.created_at, last_login_at=u.last_login_at) for u in rows]
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.post("/users", response_model=UserOut)
def create_user(
    payload: UserCreateRequest,
    admin: AppUser = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> UserOut:
    role = db.query(Role).filter(Role.name == payload.role).one_or_none()
    if role is None:
        raise ApiError(422, "INVALID_ROLE", "role must be analyst, supervisor or admin")
    if db.query(AppUser).filter(AppUser.email == payload.email).one_or_none() is not None:
        raise ApiError(409, "EMAIL_TAKEN", "A user with this email already exists")

    user = AppUser(
        role_id=role.role_id, full_name=payload.full_name, email=payload.email,
        password_hash=hash_password(payload.temporary_password), is_active=True,
    )
    db.add(user)
    db.flush()
    audit(db, action="USER_CREATED", entity="app_user", entity_id=str(user.user_id), user=admin,
          details={"email": payload.email, "role": payload.role})
    db.commit()
    return UserOut(user_id=user.user_id, full_name=user.full_name, email=user.email, role=user.role_name,
                    is_active=user.is_active, created_at=user.created_at, last_login_at=user.last_login_at)


@router.get("/users/{user_id}", response_model=UserOut)
def get_user(
    user_id: uuid.UUID,
    admin: AppUser = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> UserOut:
    user = db.get(AppUser, user_id)
    if user is None:
        raise ApiError(404, "NOT_FOUND", "User not found")
    return UserOut(user_id=user.user_id, full_name=user.full_name, email=user.email, role=user.role_name,
                    is_active=user.is_active, created_at=user.created_at, last_login_at=user.last_login_at)


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdateRequest,
    admin: AppUser = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> UserOut:
    user = db.get(AppUser, user_id)
    if user is None:
        raise ApiError(404, "NOT_FOUND", "User not found")

    if payload.is_active is False and user.user_id == admin.user_id:
        raise ApiError(422, "CANNOT_DEACTIVATE_SELF", "You cannot deactivate your own account")

    before = {"full_name": user.full_name, "role": user.role_name, "is_active": user.is_active}
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.role is not None:
        role = db.query(Role).filter(Role.name == payload.role).one_or_none()
        if role is None:
            raise ApiError(422, "INVALID_ROLE", "role must be analyst, supervisor or admin")
        user.role_id = role.role_id
    was_deactivated = payload.is_active is False and user.is_active
    if payload.is_active is not None:
        user.is_active = payload.is_active

    if was_deactivated:
        open_cases = db.execute(
            select(FraudCase).where(
                FraudCase.assigned_to == user.user_id,
                FraudCase.status.in_(("NEW", "ASSIGNED", "UNDER_INVESTIGATION", "ESCALATED")),
            )
        ).scalars().all()
        for case in open_cases:
            case.assigned_to = None
            case.status = "NEW"
            db.add(CaseNote(case_id=case.case_id, user_id=None,
                             note=f"Unassigned automatically: {user.full_name} was deactivated", note_type="SYSTEM"))

    audit(db, action="USER_UPDATED", entity="app_user", entity_id=str(user.user_id), user=admin,
          details={"before": before, "after": {"full_name": user.full_name, "role": user.role_name, "is_active": user.is_active}})
    db.commit()
    return UserOut(user_id=user.user_id, full_name=user.full_name, email=user.email, role=user.role_name,
                    is_active=user.is_active, created_at=user.created_at, last_login_at=user.last_login_at)


@router.post("/users/{user_id}/reset-password", response_model=ResetPasswordResponse)
def reset_password(
    user_id: uuid.UUID,
    admin: AppUser = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> ResetPasswordResponse:
    user = db.get(AppUser, user_id)
    if user is None:
        raise ApiError(404, "NOT_FOUND", "User not found")
    temp_password = _random_password()
    user.password_hash = hash_password(temp_password)
    audit(db, action="PASSWORD_RESET", entity="app_user", entity_id=str(user.user_id), user=admin)
    db.commit()
    return ResetPasswordResponse(temporary_password=temp_password)


@router.get("/settings", response_model=SettingsOut)
def get_settings_endpoint(
    admin: AppUser = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> SettingsOut:
    return SettingsOut(**get_settings_dict(db))


@router.put("/settings", response_model=SettingsOut)
def put_settings(
    payload: SettingsUpdate,
    admin: AppUser = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> SettingsOut:
    merged = update_settings(db, payload.model_dump(exclude_unset=True), updated_by=admin.email)
    audit(db, action="SETTINGS_UPDATED", entity="system_setting", entity_id="system_settings", user=admin,
          details=merged)
    db.commit()
    return SettingsOut(**merged)


@router.get("/models", response_model=list[ModelVersionOut])
def list_models(
    admin: AppUser = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> list[ModelVersionOut]:
    rows = db.execute(select(ModelVersion).order_by(ModelVersion.version.desc())).scalars().all()
    return [ModelVersionOut(model_id=m.model_id, algorithm=m.algorithm, version=m.version, metrics=m.metrics,
                             deployed_on=m.deployed_on, is_active=m.is_active) for m in rows]


@router.post("/models/{model_id}/activate")
def activate_model(
    model_id: uuid.UUID,
    admin: AppUser = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> dict:
    model_version = db.get(ModelVersion, model_id)
    if model_version is None:
        raise ApiError(404, "NOT_FOUND", "Model version not found")

    try:
        model_registry.activate(model_version)
    except Exception as exc:
        raise ApiError(422, "MODEL_ACTIVATION_FAILED", f"Could not activate model: {exc}") from exc

    db.query(ModelVersion).filter(ModelVersion.is_active.is_(True)).update({"is_active": False})
    model_version.is_active = True
    model_version.deployed_on = datetime.now(timezone.utc)
    audit(db, action="MODEL_ACTIVATED", entity="model_version", entity_id=str(model_version.model_id), user=admin,
          details={"version": model_version.version})
    db.commit()
    return {"detail": f"Activated {model_version.version}"}


@router.get("/audit-logs", response_model=Page[AuditLogOut])
def list_audit_logs(
    user_id: uuid.UUID | None = None,
    action: str | None = None,
    entity: str | None = None,
    from_: datetime | None = None,
    to: datetime | None = None,
    page: int = 1,
    page_size: int = 25,
    admin: AppUser = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> Page[AuditLogOut]:
    from app.models.audit import AuditLog

    page_size = min(page_size, 100)
    query = select(AuditLog)
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
    if action:
        query = query.where(AuditLog.action == action)
    if entity:
        query = query.where(AuditLog.entity == entity)
    if from_:
        query = query.where(AuditLog.timestamp >= from_)
    if to:
        query = query.where(AuditLog.timestamp <= to)

    from sqlalchemy import func

    total = db.execute(select(func.count()).select_from(query.subquery())).scalar_one()
    query = query.order_by(AuditLog.timestamp.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = db.execute(query).scalars().all()
    items = [AuditLogOut.model_validate(r, from_attributes=True) for r in rows]
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.get("/labels/export")
def export_labels(
    admin: AppUser = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> Response:
    from app.models.ml import Prediction
    from fraud_core.constants import FEATURE_NAMES

    rows = db.execute(
        select(FraudCase, Prediction)
        .join(Txn, Txn.txn_id == FraudCase.txn_id)
        .join(Prediction, Prediction.txn_id == Txn.txn_id)
        .where(FraudCase.outcome.in_(("confirmed_fraud", "false_positive")))
    ).all()

    import csv

    buf = io.StringIO()
    fieldnames = ["txn_ref", "case_number", "label", *FEATURE_NAMES]
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for case, prediction in rows:
        txn = db.get(Txn, prediction.txn_id)
        row = {"txn_ref": txn.txn_ref, "case_number": case.case_number,
               "label": 1 if case.outcome == "confirmed_fraud" else 0}
        row.update({name: prediction.features.get(name) for name in FEATURE_NAMES})
        writer.writerow(row)

    return Response(buf.getvalue().encode("utf-8"), media_type="text/csv",
                     headers={"Content-Disposition": "attachment; filename=labels_export.csv"})
