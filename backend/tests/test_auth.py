"""Login success/failure/lockout and role restrictions (Section 15.3)."""
from __future__ import annotations

from app.core.rate_limit import login_rate_limiter
from app.core.security import login_throttle
from tests.conftest import auth_headers, make_user


def test_login_success(client, db_session, roles):
    make_user(db_session, roles, "admin", "admin@test.local")
    resp = client.post("/api/v1/auth/login", json={"email": "admin@test.local", "password": "Password1234"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["user"]["role"] == "admin"
    assert body["token_type"] == "bearer"


def test_login_wrong_password(client, db_session, roles):
    make_user(db_session, roles, "admin", "admin2@test.local")
    resp = client.post("/api/v1/auth/login", json={"email": "admin2@test.local", "password": "wrong"})
    assert resp.status_code == 401
    assert resp.json()["code"] == "INVALID_CREDENTIALS"


def test_login_lockout_after_5_failures(client, db_session, roles):
    login_throttle.reset("lockme@test.local")
    make_user(db_session, roles, "admin", "lockme@test.local")
    for _ in range(5):
        client.post("/api/v1/auth/login", json={"email": "lockme@test.local", "password": "wrong"})
    # The 5/minute login rate limit (keyed by client IP) and the 5-attempt
    # lockout (keyed by email) use the same threshold; clear the rate limiter
    # here so this request exercises the lockout check specifically.
    login_rate_limiter._hits.clear()
    resp = client.post("/api/v1/auth/login", json={"email": "lockme@test.local", "password": "Password1234"})
    assert resp.status_code == 423
    assert resp.json()["code"] == "ACCOUNT_LOCKED"
    login_throttle.reset("lockme@test.local")


def test_me_requires_token(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_role_restriction_forbidden(client, db_session, roles):
    make_user(db_session, roles, "analyst", "analyst@test.local")
    headers = auth_headers(client, "analyst@test.local")
    resp = client.get("/api/v1/admin/users", headers=headers)
    assert resp.status_code == 403
    assert resp.json()["code"] == "FORBIDDEN"


def test_change_password_validates_strength(client, db_session, roles):
    make_user(db_session, roles, "analyst", "pwchange@test.local")
    headers = auth_headers(client, "pwchange@test.local")
    resp = client.post("/api/v1/auth/change-password", json={"current_password": "Password1234", "new_password": "short"},
                        headers=headers)
    assert resp.status_code == 422
