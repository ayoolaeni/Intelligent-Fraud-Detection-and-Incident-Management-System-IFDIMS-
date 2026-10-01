"""Display masks for sensitive identifiers (Section 12.2)."""
from __future__ import annotations

import hashlib

from app.config import get_settings


def mask_account_number(account_number: str) -> str:
    if len(account_number) <= 4:
        return "*" * len(account_number)
    return "*" * (len(account_number) - 4) + account_number[-4:]


def mask_phone(phone_last4: str) -> str:
    return f"****{phone_last4}"


def hash_bvn(bvn: str) -> str:
    settings = get_settings()
    return hashlib.sha256((settings.bvn_salt + bvn).encode("utf-8")).hexdigest()


def hash_phone(phone: str) -> str:
    settings = get_settings()
    return hashlib.sha256((settings.phone_salt + phone).encode("utf-8")).hexdigest()
