"""Tests for the auto-registration half of app.seed (Section 14 / D25):
a fresh clone + docker compose up should activate a committed model
bundle automatically, with no manual `register_model` step."""
from __future__ import annotations

import json

from app.models.ml import ModelVersion
from app.seed import seed_model_if_needed


def _write_bundle(tmp_path, version: str):
    bundle_dir = tmp_path / version
    bundle_dir.mkdir()
    (bundle_dir / "metadata.json").write_text(json.dumps({"algorithm": "xgboost", "version": version}))
    (bundle_dir / "model.joblib").write_bytes(b"not a real bundle, only existence is checked")
    return bundle_dir


def test_registers_and_activates_the_only_bundle_when_nothing_is_active(db_session, tmp_path):
    _write_bundle(tmp_path, "20260101-0000-xgboost")

    seed_model_if_needed(db_session, str(tmp_path))

    active = db_session.query(ModelVersion).filter(ModelVersion.is_active.is_(True)).one()
    assert active.version == "20260101-0000-xgboost"
    assert active.algorithm == "xgboost"
    assert active.deployed_on is not None


def test_picks_the_chronologically_latest_bundle(db_session, tmp_path):
    _write_bundle(tmp_path, "20260101-0000-xgboost")
    _write_bundle(tmp_path, "20260601-0000-random_forest")

    seed_model_if_needed(db_session, str(tmp_path))

    active = db_session.query(ModelVersion).filter(ModelVersion.is_active.is_(True)).one()
    assert active.version == "20260601-0000-random_forest"


def test_does_nothing_when_a_model_is_already_active(db_session, tmp_path):
    _write_bundle(tmp_path, "20260101-0000-xgboost")
    existing = ModelVersion(algorithm="xgboost", version="already-active", path="already-active", metrics={}, is_active=True)
    db_session.add(existing)
    db_session.commit()

    seed_model_if_needed(db_session, str(tmp_path))

    active_versions = [m.version for m in db_session.query(ModelVersion).filter(ModelVersion.is_active.is_(True)).all()]
    assert active_versions == ["already-active"]


def test_is_a_no_op_when_no_bundle_exists(db_session, tmp_path):
    seed_model_if_needed(db_session, str(tmp_path))

    assert db_session.query(ModelVersion).count() == 0
