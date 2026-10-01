"""Admin: create user, deactivate user unassigns open cases, settings
update changes live bands, model activation (hot swap + invalid rejected)
(Section 15.3).
"""
from __future__ import annotations

from datetime import datetime, timezone

from tests.conftest import auth_headers, make_account, make_user

API_KEY_HEADERS = {"X-API-Key": "test-api-key"}


def test_create_user(client, db_session, roles):
    make_user(db_session, roles, "admin", "admin1@test.local")
    headers = auth_headers(client, "admin1@test.local")
    resp = client.post("/api/v1/admin/users", json={
        "full_name": "New Analyst", "email": "newanalyst@test.local", "role": "analyst",
        "temporary_password": "Temp1234567",
    }, headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["role"] == "analyst"


def test_create_user_duplicate_email_rejected(client, db_session, roles):
    make_user(db_session, roles, "admin", "admin2@test.local")
    headers = auth_headers(client, "admin2@test.local")
    payload = {"full_name": "X", "email": "dup@test.local", "role": "analyst", "temporary_password": "Temp1234567"}
    client.post("/api/v1/admin/users", json=payload, headers=headers)
    resp = client.post("/api/v1/admin/users", json=payload, headers=headers)
    assert resp.status_code == 409
    assert resp.json()["code"] == "EMAIL_TAKEN"


def test_cannot_deactivate_self(client, db_session, roles):
    admin = make_user(db_session, roles, "admin", "self@test.local")
    headers = auth_headers(client, "self@test.local")
    resp = client.patch(f"/api/v1/admin/users/{admin.user_id}", json={"is_active": False}, headers=headers)
    assert resp.status_code == 422
    assert resp.json()["code"] == "CANNOT_DEACTIVATE_SELF"


def test_deactivate_user_unassigns_open_cases(client, db_session, roles):
    make_account(db_session, account_number="2200000001")
    admin = make_user(db_session, roles, "admin", "admin3@test.local")
    analyst = make_user(db_session, roles, "analyst", "an3@test.local")
    admin_headers = auth_headers(client, "admin3@test.local")

    from app.services import case_service
    from app.services.settings_service import DEFAULT_SETTINGS

    case = case_service.create_manual_case(
        db_session, source="MANUAL", title="t", description="d", account_number="2200000001",
        txn_id=None, amount_at_risk=1000, priority="medium", settings=DEFAULT_SETTINGS, created_by=admin,
    )
    case_service.assign(db_session, case, analyst, admin)
    db_session.commit()
    assert case.status == "ASSIGNED"

    resp = client.patch(f"/api/v1/admin/users/{analyst.user_id}", json={"is_active": False}, headers=admin_headers)
    assert resp.status_code == 200, resp.text

    db_session.refresh(case)
    assert case.assigned_to is None
    assert case.status == "NEW"


def test_settings_validation_rejects_bad_thresholds(client, db_session, roles):
    make_user(db_session, roles, "admin", "admin4@test.local")
    headers = auth_headers(client, "admin4@test.local")
    resp = client.put("/api/v1/admin/settings", json={"risk_threshold_medium": 0.8, "risk_threshold_high": 0.5},
                       headers=headers)
    assert resp.status_code == 422
    assert resp.json()["code"] == "INVALID_SETTINGS"


def test_settings_update_changes_live_scoring_band(client, db_session, roles, active_model):
    make_account(db_session, account_number="2200000002")
    make_user(db_session, roles, "admin", "admin5@test.local")
    headers = auth_headers(client, "admin5@test.local")

    score_payload = {
        "account_number": "2200000002", "amount": "1000.00", "channel": "NIP",
        "txn_type": "TRANSFER", "txn_time": datetime.now(timezone.utc).isoformat(),
        "beneficiary_account": "111", "beneficiary_bank": "058", "device_id": "dev-1",
        "location": "Lagos", "balance_before": "500000.00",
    }
    first = client.post("/api/v1/transactions/score", json={**score_payload, "txn_ref": "SETTINGS-1"},
                         headers=API_KEY_HEADERS)
    assert first.status_code == 200, first.text
    score = first.json()["fraud_score"]
    assert score > 0

    # Push both thresholds below the observed score so the *same* pattern
    # now qualifies as high, proving the settings change took live effect.
    # (medium < high < score, so risk_band ends up "high" for this score.)
    resp = client.put("/api/v1/admin/settings", json={
        "risk_threshold_medium": score * 0.25, "risk_threshold_high": score * 0.5,
    }, headers=headers)
    assert resp.status_code == 200, resp.text

    second = client.post("/api/v1/transactions/score", json={**score_payload, "txn_ref": "SETTINGS-2"},
                          headers=API_KEY_HEADERS)
    assert second.status_code == 200, second.text
    assert second.json()["risk_band"] == "high"


def test_refresh_if_changed_picks_up_activation_from_another_worker(client, db_session, roles, active_model):
    """Regression test for docs/DECISIONS.md D23: with multiple uvicorn
    worker processes, each has its own model_registry singleton, so
    activating a model via one worker must still converge on the others
    within a few seconds via refresh_if_changed(), not require a restart.
    """
    from app.services.model_registry import ModelRegistry

    # A second registry instance simulates a different worker process that
    # hasn't seen today's activation yet.
    other_worker_registry = ModelRegistry()
    other_worker_registry.load_active_from_db(db_session)
    assert other_worker_registry.loaded.version == active_model.version

    # Simulate training+registering+activating a newer model purely at the
    # database level (as admin.py's activate endpoint would, from a
    # *different* worker's request).
    import shutil

    from app.config import get_settings
    from app.models.ml import ModelVersion
    from tests.conftest import _train_tiny_fixture_model
    import joblib, os, uuid as uuid_module

    new_version = f"test-fixture-{uuid_module.uuid4().hex[:8]}"
    bundle = _train_tiny_fixture_model()
    bundle["version"] = new_version
    version_dir = os.path.join(get_settings().models_dir, new_version)
    os.makedirs(version_dir, exist_ok=True)
    joblib.dump(bundle, os.path.join(version_dir, "model.joblib"))

    db_session.query(ModelVersion).filter(ModelVersion.is_active.is_(True)).update({"is_active": False})
    new_row = ModelVersion(algorithm="xgboost", version=new_version, path=new_version, metrics={}, is_active=True)
    db_session.add(new_row)
    db_session.commit()

    assert other_worker_registry.loaded.version == active_model.version  # still stale
    other_worker_registry.refresh_if_changed(db_session)
    assert other_worker_registry.loaded.version == new_version  # converged

    shutil.rmtree(version_dir, ignore_errors=True)


def test_activate_invalid_model_rejected(client, db_session, roles):
    make_user(db_session, roles, "admin", "admin6@test.local")
    headers = auth_headers(client, "admin6@test.local")

    from app.models.ml import ModelVersion

    bad_model = ModelVersion(algorithm="xgboost", version="bad-version-does-not-exist",
                              path="bad-version-does-not-exist", metrics={}, is_active=False)
    db_session.add(bad_model)
    db_session.commit()

    resp = client.post(f"/api/v1/admin/models/{bad_model.model_id}/activate", headers=headers)
    assert resp.status_code == 422
    assert resp.json()["code"] == "MODEL_ACTIVATION_FAILED"

    db_session.refresh(bad_model)
    assert bad_model.is_active is False
