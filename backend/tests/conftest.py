"""Shared pytest fixtures: an isolated test database, a FastAPI TestClient
wired to it, and helper factories for roles/users (Section 15.3).
"""
from __future__ import annotations

import os
import sys
import uuid

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ML_DIR = os.path.join(_BACKEND_DIR, "..", "ml")
if _ML_DIR not in sys.path:
    sys.path.insert(0, _ML_DIR)

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://ifdims:ifdims@localhost:55432/ifdims_test")
os.environ.setdefault("JWT_SECRET", "test-secret-at-least-32-characters-long")
os.environ.setdefault("BVN_SALT", "test-bvn-salt")
os.environ.setdefault("PHONE_SALT", "test-phone-salt")
os.environ.setdefault("SERVICE_API_KEYS", "test:test-api-key")
os.environ.setdefault("ATTACHMENTS_DIR", "./test_attachments")
os.environ.setdefault("MODELS_DIR", "../models")
os.environ.setdefault("SEED_DEMO_USERS", "false")

import pytest
import sqlalchemy
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

ADMIN_DB_URL = "postgresql+psycopg://ifdims:ifdims@localhost:55432/ifdims"
TEST_DB_NAME = "ifdims_test"
TEST_DB_URL = f"postgresql+psycopg://ifdims:ifdims@localhost:55432/{TEST_DB_NAME}"


@pytest.fixture(scope="session", autouse=True)
def _test_database():
    admin_engine = create_engine(ADMIN_DB_URL, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME} WITH (FORCE)"))
        conn.execute(text(f"CREATE DATABASE {TEST_DB_NAME}"))
    admin_engine.dispose()

    from alembic import command
    from alembic.config import Config

    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = Config(os.path.join(backend_dir, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(backend_dir, "alembic"))
    cfg.set_main_option("sqlalchemy.url", TEST_DB_URL)
    command.upgrade(cfg, "head")

    yield

    admin_engine = create_engine(ADMIN_DB_URL, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME} WITH (FORCE)"))
    admin_engine.dispose()


@pytest.fixture(scope="session")
def engine(_test_database):
    return create_engine(TEST_DB_URL, future=True)


@pytest.fixture()
def db_session(engine):
    connection = engine.connect()
    outer_transaction = connection.begin()
    # join_transaction_mode="create_savepoint": the app code's own
    # db.commit() calls inside endpoints commit a SAVEPOINT, not the outer
    # transaction, so the whole test's changes can still be rolled back here.
    TestSessionLocal = sessionmaker(
        bind=connection, autoflush=False, autocommit=False, future=True,
        join_transaction_mode="create_savepoint",
    )
    session = TestSessionLocal()

    yield session

    session.close()
    outer_transaction.rollback()
    connection.close()


@pytest.fixture(autouse=True)
def _reset_rate_limits_and_throttle():
    """Rate limiter and login throttle are process-wide singletons; reset
    them before every test so tests don't interfere with each other."""
    from app.core.rate_limit import login_rate_limiter, scoring_rate_limiter
    from app.core.security import login_throttle

    login_rate_limiter._hits.clear()
    scoring_rate_limiter._hits.clear()
    login_throttle._failures.clear()
    login_throttle._locked_until.clear()
    yield


@pytest.fixture()
def client(db_session, monkeypatch):
    from fastapi.testclient import TestClient

    from app.db import get_db
    from app.main import app

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def roles(db_session):
    from app.models.user import Role

    result = {}
    for name in ("analyst", "supervisor", "admin"):
        role = Role(name=name, permissions=[])
        db_session.add(role)
        db_session.flush()
        result[name] = role
    db_session.commit()
    return result


def make_user(db_session, roles, role_name: str, email: str, password: str = "Password1234"):
    from app.core.security import hash_password
    from app.models.user import AppUser

    user = AppUser(role_id=roles[role_name].role_id, full_name=email.split("@")[0],
                    email=email, password_hash=hash_password(password), is_active=True)
    db_session.add(user)
    db_session.commit()
    return user


def auth_headers(client, email: str, password: str = "Password1234") -> dict:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def make_account(db_session, *, account_number: str = "2000000001", opened_days_ago: int = 400):
    import datetime as dt

    from app.models.customer import Account, Customer

    customer = Customer(
        bvn_hash="x" * 64, full_name="Test Customer", phone_hash="y" * 64, phone_last4="1234",
        date_joined=dt.date.today() - dt.timedelta(days=opened_days_ago), risk_profile="low",
    )
    db_session.add(customer)
    db_session.flush()
    account = Account(
        customer_id=customer.customer_id, account_number=account_number, account_type="SAVINGS",
        opened_on=dt.date.today() - dt.timedelta(days=opened_days_ago), status="ACTIVE",
    )
    db_session.add(account)
    db_session.commit()
    return account


def _train_tiny_fixture_model():
    """A tiny but real XGBoost model (Section 15.3: "train a tiny XGBoost on
    a fixture dataset in the test setup"), wired so is_new_beneficiary and
    amount_to_avg_30d drive the score predictably: high score needs both a
    new beneficiary AND an unusually large amount; medium score needs one of
    the two; everything else scores low. This lets tests reliably produce
    low/medium/high transactions without depending on a real trained model.
    """
    import numpy as np
    import pandas as pd
    from sklearn.pipeline import Pipeline
    from xgboost import XGBClassifier

    from fraud_core.constants import FEATURE_NAMES

    rng = np.random.default_rng(42)
    n = 400
    rows = []
    labels = []
    for _ in range(n):
        row = {name: 0.0 for name in FEATURE_NAMES}
        is_new_bene = rng.random() < 0.5
        amount_ratio = float(rng.uniform(0.5, 30.0))
        row["log_amount"] = float(np.log1p(rng.uniform(1000, 500000)))
        row["amount_to_avg_30d"] = amount_ratio
        row["is_new_beneficiary"] = 1.0 if is_new_bene else 0.0
        row["is_new_device"] = 0.0
        row["is_night"] = 0.0
        row["day_of_week"] = float(rng.integers(0, 7))
        row["channel_NIP"] = 1.0
        row["txn_count_1h"] = 0.0
        row["txn_count_24h"] = float(rng.integers(0, 3))
        # Covers the full range compute_features_online can actually return,
        # including the no-history defaults (mins_since_last_txn capped at
        # 43200, balance_ratio up to 1.0) that every no-history test payload
        # hits -- training on a narrower range left the model's decision
        # boundary fragile/spuriously sensitive to those out-of-distribution
        # values in a handful of tests.
        row["mins_since_last_txn"] = float(rng.uniform(60, 43200))
        row["account_age_days"] = float(rng.uniform(30, 2000))
        row["balance_ratio"] = float(rng.uniform(0.05, 1.0))
        risky = int(is_new_bene) + int(amount_ratio > 10)
        label = 1 if risky >= 2 else 0
        rows.append(row)
        labels.append(label)

    X = pd.DataFrame(rows)[FEATURE_NAMES]
    y = pd.Series(labels)

    clf = XGBClassifier(n_estimators=50, max_depth=3, tree_method="hist", eval_metric="logloss", random_state=42)
    pipeline = Pipeline([("clf", clf)])
    pipeline.fit(X, y)

    import shap

    explainer = shap.TreeExplainer(clf)

    bundle = {
        "estimator": pipeline,
        "feature_names": FEATURE_NAMES,
        "global_median_amount": 15000.0,
        "algorithm": "xgboost",
        "version": None,  # filled in by the fixture
        "trained_at": "test-fixture",
        "suggested_thresholds": {"suggested_medium_threshold": 0.40, "suggested_high_threshold": 0.70},
        "shap_expected_value": float(np.ravel(explainer.expected_value)[-1]),
        "shap_explainer_kind": "tree",
        "shap_background_sample": X.sample(n=50, random_state=42),
    }
    return bundle


@pytest.fixture()
def active_model(db_session):
    """Registers and activates a tiny real XGBoost model as the active
    model, so /transactions/score can be exercised end-to-end.
    """
    import shutil
    import uuid as uuid_module

    import joblib

    from app.config import get_settings
    from app.models.ml import ModelVersion
    from app.services.model_registry import model_registry

    version = f"test-fixture-{uuid_module.uuid4().hex[:8]}"
    bundle = _train_tiny_fixture_model()
    bundle["version"] = version

    models_dir = get_settings().models_dir
    version_dir = os.path.join(models_dir, version)
    os.makedirs(version_dir, exist_ok=True)
    joblib.dump(bundle, os.path.join(version_dir, "model.joblib"))

    model_row = ModelVersion(algorithm="xgboost", version=version, path=version, metrics={}, is_active=True)
    db_session.add(model_row)
    db_session.commit()

    model_registry.activate(model_row)

    yield model_row

    model_registry._loaded = None
    shutil.rmtree(version_dir, ignore_errors=True)
