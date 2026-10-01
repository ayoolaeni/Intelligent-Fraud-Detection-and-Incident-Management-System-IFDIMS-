"""Idempotent seed: roles, admin user, demo users, default settings
(Section 14). Run with: python -m app.seed
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.config import get_settings
from app.core.security import hash_password
from app.db import SessionLocal
from app.models.ml import ModelVersion
from app.models.user import AppUser, Role
from app.services.settings_service import seed_default_settings

ROLE_NAMES = ("analyst", "supervisor", "admin")

DEMO_USERS = [
    ("supervisor@ifdims.local", "Demo Supervisor", "supervisor"),
    ("analyst1@ifdims.local", "Demo Analyst One", "analyst"),
    ("analyst2@ifdims.local", "Demo Analyst Two", "analyst"),
]
DEMO_PASSWORD = "Demo12345!"


def run() -> None:
    settings = get_settings()
    db = SessionLocal()
    try:
        roles = {}
        for name in ROLE_NAMES:
            role = db.query(Role).filter(Role.name == name).one_or_none()
            if role is None:
                role = Role(name=name, permissions=[])
                db.add(role)
                db.flush()
            roles[name] = role

        admin = db.query(AppUser).filter(AppUser.email == settings.admin_email).one_or_none()
        if admin is None:
            db.add(AppUser(
                role_id=roles["admin"].role_id,
                full_name="Administrator",
                email=settings.admin_email,
                password_hash=hash_password(settings.admin_password),
                is_active=True,
            ))
            print(f"Created admin user {settings.admin_email}")

        if settings.seed_demo_users:
            for email, full_name, role_name in DEMO_USERS:
                existing = db.query(AppUser).filter(AppUser.email == email).one_or_none()
                if existing is None:
                    db.add(AppUser(
                        role_id=roles[role_name].role_id,
                        full_name=full_name,
                        email=email,
                        password_hash=hash_password(DEMO_PASSWORD),
                        is_active=True,
                    ))
                    print(f"Created demo user {email}")

        seed_default_settings(db)
        db.commit()

        seed_model_if_needed(db, settings.models_dir)
        print("Seed complete.")
    finally:
        db.close()


def seed_model_if_needed(db, models_dir: str) -> None:
    """On a fresh clone/deploy there is no model_version row yet, but a
    trained model bundle is committed under ``models/`` (unlike every other
    future training run, which stays gitignored). Auto-register and
    activate it so the system scores transactions immediately after
    ``docker compose up``, with no manual ``register_model`` step required.
    """
    if db.query(ModelVersion).filter(ModelVersion.is_active.is_(True)).first() is not None:
        return

    candidates = []
    for metadata_path in sorted(Path(models_dir).glob("*/metadata.json")):
        bundle_dir = metadata_path.parent
        if (bundle_dir / "model.joblib").exists():
            candidates.append(bundle_dir)
    if not candidates:
        print("No active model and no model bundle found under models/ — scoring will be unavailable until one is registered.")
        return

    bundle_dir = candidates[-1]  # version folders sort chronologically (YYYYMMDD-HHMM-algorithm)
    metadata = json.loads((bundle_dir / "metadata.json").read_text())
    version = metadata["version"]

    model_version = db.query(ModelVersion).filter(ModelVersion.version == version).one_or_none()
    if model_version is None:
        model_version = ModelVersion(
            algorithm=metadata["algorithm"],
            version=version,
            path=bundle_dir.name,
            metrics=metadata,
        )
        db.add(model_version)
        db.flush()

    model_version.is_active = True
    model_version.deployed_on = datetime.now(timezone.utc)
    db.commit()
    print(f"Auto-registered and activated model {version} from {bundle_dir}")


if __name__ == "__main__":
    run()
