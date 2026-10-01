"""Authentication and role-based access dependencies (Section 9). The back
end is the authority: the front end only hides unavailable actions.
"""
from __future__ import annotations

import jwt as pyjwt
from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.security import check_api_key, decode_access_token
from app.db import get_db
from app.models.user import AppUser

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> AppUser:
    if credentials is None:
        raise ApiError(401, "NOT_AUTHENTICATED", "Not authenticated")
    try:
        payload = decode_access_token(credentials.credentials)
    except pyjwt.ExpiredSignatureError as exc:
        raise ApiError(401, "TOKEN_EXPIRED", "Session expired, please log in again") from exc
    except pyjwt.InvalidTokenError as exc:
        raise ApiError(401, "INVALID_TOKEN", "Invalid authentication token") from exc

    user = db.get(AppUser, payload["sub"])
    if user is None or not user.is_active:
        raise ApiError(401, "INVALID_USER", "User not found or inactive")
    return user


def require_roles(*roles: str):
    def dependency(user: AppUser = Depends(get_current_user)) -> AppUser:
        if user.role_name not in roles:
            raise ApiError(403, "FORBIDDEN", "You do not have permission to perform this action")
        return user

    return dependency


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> str:
    name = check_api_key(x_api_key)
    if name is None:
        raise ApiError(401, "INVALID_API_KEY", "Missing or invalid API key")
    return name
