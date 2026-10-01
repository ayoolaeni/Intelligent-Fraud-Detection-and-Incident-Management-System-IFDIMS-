"""Consistent error responses: {"detail": "...", "code": "..."} (Section 8)."""
from __future__ import annotations

from fastapi import HTTPException


class ApiError(HTTPException):
    def __init__(self, status_code: int, code: str, detail: str) -> None:
        super().__init__(status_code=status_code, detail={"detail": detail, "code": code})
