# Sprint 3 — Transactions scored in real time (US3, US4)

## Built

- Full Postgres schema (Section 7) via Alembic: all 15 tables, every index
  from Section 7.3, the `fraud_case_seq` sequence, a partial unique index
  enforcing exactly one active model, and an append-only trigger on
  `audit_log` (a single shared DB role makes a literal `REVOKE` a no-op for
  the owner — see `docs/DECISIONS.md` D18).
- `app/services/feature_service.py`: the four Section 7.4 queries plus
  `compute_features_for_txn`, calling `fraud_core.features.compute_features_online`.
- `app/services/model_registry.py`: loads/hot-swaps the active model bundle,
  rebuilds its SHAP explainer, refuses to load if `feature_names` doesn't
  match `FEATURE_NAMES`.
- `app/services/scoring_service.py`: SHAP contribution ordering (increasing
  factors first, by absolute contribution), `hour_sin`/`hour_cos` merging,
  risk banding from live settings.
- `POST /transactions/score`, `POST /security-events`,
  `GET /transactions`, `GET /transactions/{id}`,
  `POST /transactions/{id}/release|decline`.

## Bug found and fixed during this sprint

Every `Mapped[datetime]` column defaulted to Postgres's naive
`TIMESTAMP WITHOUT TIME ZONE` instead of the spec's required `TIMESTAMPTZ`,
because SQLAlchemy 2.0 doesn't infer `timezone=True` from the type
annotation alone. Fixed at the `Base` level with a `type_annotation_map`,
and the migration was regenerated. Caught by a `TypeError: can't compare
offset-naive and offset-aware datetimes` in the SLA-state calculation
during Sprint 4 testing.

## Tests

`backend/tests/test_scoring.py` (7 tests): 503 with no active model, 404 on
unknown account, low/medium/high banding and side effects, idempotent
replay (same `txn_id`/`prediction_id`, one row in `txn`), API-key
enforcement, security-event ingestion.

`backend/tests/test_feature_parity.py` — the **mandatory** Section 15.2
test: generates a 200-customer/14-day world, loads it into a real Postgres
test database, and for 300 randomly chosen transactions compares
`compute_features_batch`'s output against the online path
(`feature_service` reading from the database) to 1e-6. Passing.

**Done-when check**: a scored transaction returns the correct band and top
factors; the parity test passes; single-request latency (measured directly
in `pipeline.train`'s latency benchmark and observed in integration tests)
is in the tens of milliseconds, well under 500ms.
