"""Idempotent seed: roles, admin user, demo users, default settings
(Section 14). Run with: python -m app.seed
"""
from __future__ import annotations

from app.config import get_settings
from app.core.security import hash_password
from app.db import SessionLocal
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
        print("Seed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
