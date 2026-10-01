"""Case endpoints (Section 8.4)."""
from __future__ import annotations

import os
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errors import ApiError
from app.core.masking import mask_account_number
from app.core.rbac import require_roles
from app.db import get_db
from app.models.case import CaseAttachment, CaseNote, FraudCase
from app.models.customer import Account
from app.models.transaction import Txn
from app.models.user import AppUser
from app.schemas.case import (
    AssignCaseRequest,
    CaseAttachmentOut,
    CaseCreateRequest,
    CaseDetailOut,
    CaseNoteOut,
    CaseOut,
    NoteCreateRequest,
    TransitionCaseRequest,
)
from app.schemas.common import Page
from app.services import case_service
from app.services.settings_service import get_settings_dict

router = APIRouter(prefix="/cases", tags=["cases"])

MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {
    "application/pdf", "image/png", "image/jpeg", "text/csv", "text/plain",
}


def _case_out(db: Session, case: FraudCase) -> CaseOut:
    assignee = db.get(AppUser, case.assigned_to) if case.assigned_to else None
    return CaseOut(
        case_id=case.case_id,
        case_number=case.case_number,
        title=case.title,
        source=case.source,
        priority=case.priority,
        status=case.status,
        outcome=case.outcome,
        assigned_to=case.assigned_to,
        assigned_to_name=assignee.full_name if assignee else None,
        amount_at_risk=case.amount_at_risk,
        amount_recovered=case.amount_recovered,
        opened_at=case.opened_at,
        ack_due_at=case.ack_due_at,
        resolve_due_at=case.resolve_due_at,
        closed_at=case.closed_at,
        sla_state=case_service.sla_state(case),
    )


@router.get("/meta/assignable-users")
def assignable_users(
    user: AppUser = Depends(require_roles("supervisor")),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Active analysts and supervisors, for the case-assign dropdown.

    Not in the spec's endpoint list; `/admin/users` is admin-only and
    supervisors need *some* way to see who they can assign a case to
    (Section 8.4 `/cases/{id}/assign`). Documented in docs/DECISIONS.md.
    """
    from app.models.user import Role

    rows = db.execute(
        select(AppUser)
        .join(Role, Role.role_id == AppUser.role_id)
        .where(Role.name.in_(("analyst", "supervisor")), AppUser.is_active.is_(True))
        .order_by(AppUser.full_name)
    ).scalars().all()
    return [{"user_id": str(u.user_id), "full_name": u.full_name, "role": u.role_name} for u in rows]


@router.get("", response_model=Page[CaseOut])
def list_cases(
    status: str | None = None,
    priority: str | None = None,
    assigned_to: str | None = None,
    source: str | None = None,
    overdue: bool | None = None,
    from_: datetime | None = None,
    to: datetime | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = 25,
    user: AppUser = Depends(require_roles("analyst", "supervisor")),
    db: Session = Depends(get_db),
) -> Page[CaseOut]:
    page_size = min(page_size, 100)
    query = select(FraudCase)

    if user.role_name == "analyst":
        query = query.where(or_(FraudCase.assigned_to == user.user_id, FraudCase.assigned_to.is_(None)))

    if status:
        query = query.where(FraudCase.status == status)
    if priority:
        query = query.where(FraudCase.priority == priority)
    if assigned_to:
        if assigned_to == "me":
            query = query.where(FraudCase.assigned_to == user.user_id)
        else:
            query = query.where(FraudCase.assigned_to == uuid.UUID(assigned_to))
    if source:
        query = query.where(FraudCase.source == source)
    if from_:
        query = query.where(FraudCase.opened_at >= from_)
    if to:
        query = query.where(FraudCase.opened_at <= to)
    if q:
        like = f"%{q}%"
        query = query.outerjoin(Txn, Txn.txn_id == FraudCase.txn_id).outerjoin(
            Account, Account.account_id == Txn.account_id
        ).where(or_(FraudCase.case_number.ilike(like), FraudCase.title.ilike(like), Account.account_number.ilike(like)))

    total = db.execute(select(func.count()).select_from(query.subquery())).scalar_one()
    query = query.order_by(FraudCase.opened_at.desc()).offset((page - 1) * page_size).limit(page_size)
    cases = db.execute(query).scalars().all()

    items = [_case_out(db, c) for c in cases]
    if overdue:
        items = [c for c in items if c.sla_state == "breached"]
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=CaseOut)
def create_case(
    payload: CaseCreateRequest,
    user: AppUser = Depends(require_roles("analyst", "supervisor")),
    db: Session = Depends(get_db),
) -> CaseOut:
    if payload.source not in ("CUSTOMER_REPORT", "MANUAL"):
        raise ApiError(422, "INVALID_SOURCE", "source must be CUSTOMER_REPORT or MANUAL")

    txn_id = None
    if payload.txn_ref:
        txn = db.query(Txn).filter(Txn.txn_ref == payload.txn_ref).one_or_none()
        if txn is None:
            raise ApiError(404, "TXN_NOT_FOUND", "txn_ref not found")
        txn_id = txn.txn_id

    settings = get_settings_dict(db)
    case = case_service.create_manual_case(
        db, source=payload.source, title=payload.title, description=payload.description,
        account_number=payload.account_number, txn_id=txn_id, amount_at_risk=payload.amount_at_risk,
        priority=payload.priority, settings=settings, created_by=user,
    )
    db.commit()
    return _case_out(db, case)


@router.get("/{case_id}", response_model=CaseDetailOut)
def get_case(
    case_id: uuid.UUID,
    user: AppUser = Depends(require_roles("analyst", "supervisor")),
    db: Session = Depends(get_db),
) -> CaseDetailOut:
    case = db.get(FraudCase, case_id)
    if case is None:
        raise ApiError(404, "NOT_FOUND", "Case not found")

    account_number_masked = None
    if case.txn_id:
        txn = db.get(Txn, case.txn_id)
        if txn:
            account = db.get(Account, txn.account_id)
            if account:
                account_number_masked = mask_account_number(account.account_number)

    notes = []
    for note in case.notes:
        note_user = db.get(AppUser, note.user_id) if note.user_id else None
        notes.append(CaseNoteOut(
            note_id=note.note_id, user_id=note.user_id, user_name=note_user.full_name if note_user else None,
            note=note.note, note_type=note.note_type, created_at=note.created_at,
        ))
    attachments = [
        CaseAttachmentOut(
            attachment_id=a.attachment_id, file_name=a.file_name, content_type=a.content_type,
            size_bytes=a.size_bytes, uploaded_by=a.uploaded_by, created_at=a.created_at,
        )
        for a in case.attachments
    ]

    return CaseDetailOut(
        case=_case_out(db, case),
        description=case.description,
        alert_id=case.alert_id,
        txn_id=case.txn_id,
        account_number_masked=account_number_masked,
        fraud_type=case.fraud_type,
        notes=notes,
        attachments=attachments,
        allowed_transitions=case_service.allowed_transitions_for(user, case),
        can_assign=(user.role_name == "supervisor"),
        can_release_decline=(
            user.role_name == "supervisor" or (user.role_name == "analyst" and case.assigned_to == user.user_id)
        ),
    )


@router.post("/{case_id}/assign", response_model=CaseOut)
def assign_case(
    case_id: uuid.UUID,
    payload: AssignCaseRequest,
    user: AppUser = Depends(require_roles("supervisor")),
    db: Session = Depends(get_db),
) -> CaseOut:
    case = db.get(FraudCase, case_id)
    if case is None:
        raise ApiError(404, "NOT_FOUND", "Case not found")
    assignee = db.get(AppUser, payload.user_id)
    if assignee is None:
        raise ApiError(404, "USER_NOT_FOUND", "Assignee not found")
    case_service.assign(db, case, assignee, user)
    db.commit()
    return _case_out(db, case)


@router.post("/{case_id}/transition", response_model=CaseOut)
def transition_case(
    case_id: uuid.UUID,
    payload: TransitionCaseRequest,
    user: AppUser = Depends(require_roles("analyst", "supervisor")),
    db: Session = Depends(get_db),
) -> CaseOut:
    case = db.get(FraudCase, case_id)
    if case is None:
        raise ApiError(404, "NOT_FOUND", "Case not found")
    case_service.transition(
        db, case, to_status=payload.to_status, note=payload.note, acting_user=user,
        outcome=payload.outcome, fraud_type=payload.fraud_type, amount_recovered=payload.amount_recovered,
    )
    db.commit()
    return _case_out(db, case)


@router.post("/{case_id}/notes")
def add_note(
    case_id: uuid.UUID,
    payload: NoteCreateRequest,
    user: AppUser = Depends(require_roles("analyst", "supervisor")),
    db: Session = Depends(get_db),
) -> dict:
    case = db.get(FraudCase, case_id)
    if case is None:
        raise ApiError(404, "NOT_FOUND", "Case not found")
    note = CaseNote(case_id=case.case_id, user_id=user.user_id, note=payload.note, note_type="NOTE")
    db.add(note)
    from app.core.audit import audit

    audit(db, action="NOTE_ADDED", entity="fraud_case", entity_id=str(case.case_id), user=user)
    db.commit()
    return {"detail": "Note added"}


@router.post("/{case_id}/attachments")
async def upload_attachment(
    case_id: uuid.UUID,
    file: UploadFile = File(...),
    user: AppUser = Depends(require_roles("analyst", "supervisor")),
    db: Session = Depends(get_db),
) -> dict:
    case = db.get(FraudCase, case_id)
    if case is None:
        raise ApiError(404, "NOT_FOUND", "Case not found")
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise ApiError(422, "INVALID_FILE_TYPE", "Allowed types: PDF, PNG, JPG, CSV, TXT")

    content = await file.read()
    if len(content) > MAX_ATTACHMENT_BYTES:
        raise ApiError(422, "FILE_TOO_LARGE", "Attachments must be 10 MB or smaller")

    settings = get_settings()
    case_dir = os.path.join(settings.attachments_dir, str(case.case_id))
    os.makedirs(case_dir, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}_{os.path.basename(file.filename or 'upload')}"
    storage_path = os.path.join(case_dir, stored_name)
    with open(storage_path, "wb") as f:
        f.write(content)

    attachment = CaseAttachment(
        case_id=case.case_id, uploaded_by=user.user_id, file_name=file.filename or stored_name,
        content_type=file.content_type, size_bytes=len(content), storage_path=storage_path,
    )
    db.add(attachment)
    from app.core.audit import audit

    audit(db, action="ATTACHMENT_UPLOADED", entity="fraud_case", entity_id=str(case.case_id), user=user,
          details={"file_name": file.filename})
    db.commit()
    return {"attachment_id": str(attachment.attachment_id)}


@router.get("/{case_id}/attachments/{attachment_id}")
def download_attachment(
    case_id: uuid.UUID,
    attachment_id: uuid.UUID,
    user: AppUser = Depends(require_roles("analyst", "supervisor")),
    db: Session = Depends(get_db),
) -> FileResponse:
    attachment = db.get(CaseAttachment, attachment_id)
    if attachment is None or attachment.case_id != case_id:
        raise ApiError(404, "NOT_FOUND", "Attachment not found")
    return FileResponse(attachment.storage_path, filename=attachment.file_name, media_type=attachment.content_type)


@router.get("/{case_id}/history")
def case_history(
    case_id: uuid.UUID,
    user: AppUser = Depends(require_roles("analyst", "supervisor")),
    db: Session = Depends(get_db),
) -> list[dict]:
    from app.models.audit import AuditLog

    case = db.get(FraudCase, case_id)
    if case is None:
        raise ApiError(404, "NOT_FOUND", "Case not found")
    rows = db.execute(
        select(AuditLog)
        .where(AuditLog.entity == "fraud_case", AuditLog.entity_id == str(case_id))
        .order_by(AuditLog.timestamp.desc())
    ).scalars().all()
    return [
        {
            "log_id": str(r.log_id), "actor": r.actor, "action": r.action,
            "details": r.details, "timestamp": r.timestamp.isoformat(),
        }
        for r in rows
    ]
