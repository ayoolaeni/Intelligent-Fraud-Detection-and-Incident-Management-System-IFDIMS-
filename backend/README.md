# backend

FastAPI application implementing Section 8 of the build specification.

## Local development (outside Docker)

```bash
python -m venv .venv && source .venv/bin/activate   # from the repo root
pip install -r backend/requirements.txt
pip install -e ml                                    # installs fraud_core
cd backend
cp .env.example .env   # or hand-write one; see repo-root .env.example for all keys
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload
```

API docs are served at `/docs`. Health check at `/health`.

## Tests

```bash
pytest                       # needs a reachable Postgres (DATABASE_URL); a disposable
                              # ifdims_test database is created and dropped automatically
pytest -m "not slow"         # skip the feature-parity test (generates 200 customers/14 days)
pytest --cov=app --cov-report=term-missing
```

## Structure

- `app/models/` — SQLAlchemy ORM models, one file per table group.
- `app/schemas/` — Pydantic request/response models.
- `app/api/v1/` — routers (one file per resource).
- `app/core/` — security (JWT/bcrypt/API keys), RBAC dependencies, audit
  logging, rate limiting, masking.
- `app/services/` — business logic: feature loading, scoring, model
  registry (hot-swappable active model), the case state machine, alerts,
  SLA scheduler, notifications, reports, settings.
- `alembic/` — migrations. The first one also creates the `pgcrypto`
  extension, the `fraud_case_seq` sequence, the partial unique index that
  enforces exactly one active model, and the append-only trigger on
  `audit_log`.
