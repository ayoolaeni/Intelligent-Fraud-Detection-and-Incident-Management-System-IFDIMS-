"""Read/update system_setting (Section 7.2)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models.misc import SystemSetting

DEFAULT_SETTINGS: dict = {
    "risk_threshold_medium": 0.40,
    "risk_threshold_high": 0.70,
    "critical_amount_ngn": 1_000_000,
    "sla": {
        "critical": {"ack_minutes": 15, "resolve_minutes": 240},
        "high": {"ack_minutes": 30, "resolve_minutes": 1440},
        "medium": {"ack_minutes": 240, "resolve_minutes": 4320},
        "low": {"ack_minutes": 1440, "resolve_minutes": 7200},
    },
    "auto_assign": False,
    "hold_high_risk": True,
}

SETTINGS_KEY = "system_settings"


def get_settings_dict(db: Session) -> dict:
    row = db.get(SystemSetting, SETTINGS_KEY)
    if row is None:
        return dict(DEFAULT_SETTINGS)
    merged = dict(DEFAULT_SETTINGS)
    merged.update(row.value)
    return merged


def seed_default_settings(db: Session) -> None:
    row = db.get(SystemSetting, SETTINGS_KEY)
    if row is None:
        db.add(SystemSetting(key=SETTINGS_KEY, value=DEFAULT_SETTINGS, updated_by="system"))


def validate_settings(new_values: dict) -> None:
    medium = new_values["risk_threshold_medium"]
    high = new_values["risk_threshold_high"]
    if not (0 < medium < high < 1):
        raise ApiError(
            422, "INVALID_SETTINGS",
            "risk_threshold_medium and risk_threshold_high must satisfy 0 < medium < high < 1",
        )


def update_settings(db: Session, updates: dict, updated_by: str) -> dict:
    current = get_settings_dict(db)
    merged = dict(current)
    for key, value in updates.items():
        if value is None:
            continue
        if key == "sla" and isinstance(value, dict):
            sla = dict(merged.get("sla", {}))
            for priority, sla_values in value.items():
                if hasattr(sla_values, "model_dump"):
                    sla_values = sla_values.model_dump()
                sla[priority] = sla_values
            merged["sla"] = sla
        else:
            merged[key] = value

    validate_settings(merged)

    row = db.get(SystemSetting, SETTINGS_KEY)
    if row is None:
        row = SystemSetting(key=SETTINGS_KEY, value=merged, updated_by=updated_by)
        db.add(row)
    else:
        row.value = merged
        row.updated_by = updated_by
        row.updated_at = datetime.now(timezone.utc)
    return merged
