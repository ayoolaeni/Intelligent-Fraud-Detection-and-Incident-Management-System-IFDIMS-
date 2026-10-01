"""Import every ORM model so SQLAlchemy's mapper registry sees all of them
(needed for relationship() string forward-refs and for Base.metadata to be
complete when Alembic autogenerates or tests call create_all())."""
from app.models.user import Role, AppUser  # noqa: F401
from app.models.customer import Customer, Account  # noqa: F401
from app.models.transaction import Txn  # noqa: F401
from app.models.ml import ModelVersion, Prediction  # noqa: F401
from app.models.case import Alert, FraudCase, CaseNote, CaseAttachment  # noqa: F401
from app.models.misc import SecurityEvent, Notification, SystemSetting  # noqa: F401
from app.models.audit import AuditLog  # noqa: F401

__all__ = [
    "Role", "AppUser", "Customer", "Account", "Txn", "ModelVersion", "Prediction",
    "Alert", "FraudCase", "CaseNote", "CaseAttachment", "SecurityEvent",
    "Notification", "SystemSetting", "AuditLog",
]
