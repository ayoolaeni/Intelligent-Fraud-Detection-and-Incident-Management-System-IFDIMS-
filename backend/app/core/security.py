"""Password hashing, JWT issuance/verification, API key checks and the
in-memory login throttle (Section 8.1, Section 13).
"""
from __future__ import annotations

import hmac
import re
import time
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import get_settings

ALGORITHM = "HS256"
BCRYPT_ROUNDS = 12

LOCKOUT_MAX_ATTEMPTS = 5
LOCKOUT_WINDOW_SECONDS = 15 * 60
LOCKOUT_DURATION_SECONDS = 15 * 60


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def validate_password_strength(password: str) -> None:
    """Minimum 10 characters with letters and digits (Section 8.1)."""
    if len(password) < 10:
        raise ValueError("Password must be at least 10 characters long")
    if not re.search(r"[A-Za-z]", password):
        raise ValueError("Password must contain at least one letter")
    if not re.search(r"[0-9]", password):
        raise ValueError("Password must contain at least one digit")


def create_access_token(user_id: str, role: str) -> tuple[str, int]:
    settings = get_settings()
    expires_in = settings.jwt_expire_minutes * 60
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)
    return token, expires_in


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])


def check_api_key(provided_key: str | None) -> str | None:
    """Return the configured key's name if ``provided_key`` matches one of
    the SERVICE_API_KEYS, using constant-time comparison, else None.
    """
    if not provided_key:
        return None
    settings = get_settings()
    for name, key in settings.service_api_keys_map.items():
        if hmac.compare_digest(key, provided_key):
            return name
    return None


class LoginThrottle:
    """In-memory failed-login lockout (docs/DECISIONS.md D3): 5 failed
    attempts within 15 minutes locks the account for 15 minutes. Single
    FastAPI process only; not shared across replicas.
    """

    def __init__(self) -> None:
        self._failures: dict[str, list[float]] = {}
        self._locked_until: dict[str, float] = {}

    def is_locked(self, email: str) -> bool:
        locked_until = self._locked_until.get(email)
        if locked_until is None:
            return False
        if time.time() >= locked_until:
            del self._locked_until[email]
            self._failures.pop(email, None)
            return False
        return True

    def seconds_until_unlock(self, email: str) -> int:
        locked_until = self._locked_until.get(email)
        if locked_until is None:
            return 0
        return max(0, int(locked_until - time.time()))

    def record_failure(self, email: str) -> None:
        now = time.time()
        window_start = now - LOCKOUT_WINDOW_SECONDS
        attempts = [t for t in self._failures.get(email, []) if t >= window_start]
        attempts.append(now)
        self._failures[email] = attempts
        if len(attempts) >= LOCKOUT_MAX_ATTEMPTS:
            self._locked_until[email] = now + LOCKOUT_DURATION_SECONDS

    def reset(self, email: str) -> None:
        self._failures.pop(email, None)
        self._locked_until.pop(email, None)


login_throttle = LoginThrottle()
