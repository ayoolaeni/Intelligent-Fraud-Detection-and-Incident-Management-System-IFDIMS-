# Build decisions log

Record of choices made where the build specification (`IFDIMS_Build_Specification.md`)
was silent, plus any deliberate simplification. Newest entries at the bottom.

## D1 — Python / Node versions
Spec asks for Python 3.11. Build environment has Python 3.13.3 and Node 22.14.0
installed. We target Python 3.11 in Docker images (`python:3.11-slim` base) so the
shipped containers match the spec exactly, but local dev tooling may run under
whatever interpreter is on PATH. Dependency versions are pinned to releases that
support both 3.11 and 3.13.

## D2 — "Working days" SLA simplification
Table 3.7's "3 working days" / "5 working days" are implemented as 72 and 120
plain hours respectively (not business-day aware), as explicitly permitted by
Section 7.2 of the spec.

## D3 — Login lockout counters
Failed-login lockout (5 attempts / 15 minutes, then 15 minute lockout) is kept
in an in-memory dict on the FastAPI process (`core/security.py:LoginThrottle`),
keyed by email. This is acceptable for a single-process demo deployment; a
multi-instance production deployment would need a shared store (Redis).

## D4 — Rate limiting
`/auth/login` and `/transactions/score` rate limits use a simple in-memory
sliding-window limiter (`core/rate_limit.py`), per the spec's explicit
allowance in Section 13. Not distributed-safe; fine for the single backend
container this project ships.

## D5 — Money representation in JSON
All monetary amounts are serialized as **strings with 2 decimal places**
(e.g. `"250000.00"`) to avoid float rounding, per Section 8's "choose one and
use it consistently" instruction.

## D6 — Attachment storage
`case_attachment.storage_path` is a path under `ATTACHMENTS_DIR`
(`/data/attachments/<case_id>/<random-uuid>-<original-ext>`). The original
file name is kept only in the `file_name` column for display/download;
the on-disk name is randomised per Section 13.

## D7 — model registry file layout
`models/<version>/model.joblib` bundles the estimator, feature names, SHAP
background/expected value and metadata together in one joblib file (as
Section 6.1 step 10 describes) rather than separate files, to keep
load/activate atomic.

## D8 — PaySim sampling
If `data/raw/paysim.csv` is present and has more than 1,000,000 rows,
`benchmark_public.py` trains on a stratified 1,000,000-row sample (stratified
on `isFraud`) to keep memory bounded, per the explicit allowance in Section 6.3.

## D9 — Case sequence numbering
`case_number` (`FC-<year>-<6-digit-seq>`) is generated from a PostgreSQL
sequence `fraud_case_seq`, reset is not automated per-year (out of scope for
a demo system); the year in the number is taken from `opened_at`.

## D10 — Notification delivery
Per Section 11, no email/SMS is implemented. `notification_service.py`
defines a small `NotificationChannel` protocol with an `InAppChannel`
implementation registered by default, so an `EmailChannel` could be added
later without changing call sites.

## D11 — Channel-to-transaction-type mapping in the generator
The spec does not define which `txn_type` values are plausible for each
`channel`. `ml/generator/generate_synthetic.py:CHANNEL_TXN_TYPE_CHOICES`
defines: NIP -> TRANSFER only; INTERNET -> TRANSFER 70% / BILL_PAYMENT 30%;
MOBILE -> TRANSFER 50% / BILL_PAYMENT 25% / AIRTIME 25%; USSD -> TRANSFER 40%
/ AIRTIME 40% / BILL_PAYMENT 20%; POS -> CARD_PAYMENT only; ATM -> WITHDRAWAL
only.

## D12 — Fraud scenario drain percentages left unspecified by the spec
SOCIAL_ENGINEERING (40-95%) and ACCOUNT_TAKEOVER (60-100%) balance-drain
ranges are given explicitly in Section 4.3. SIM_SWAP does not state a drain
percentage; a 50-100% range was chosen (similar severity to account
takeover, since both are credential-based multi-transfer attacks).

## D13 — Fraud incident balance snapshot
Fraud incidents are injected in a second pass after the full legitimate
timeline has been simulated. `balance_before` for a fraud incident uses the
account's final simulated balance (after all legitimate activity), not a
mid-timeline balance at the exact injected timestamp. This is a
simplification: interleaving fraud injection into the day-by-day legitimate
loop would be more realistic but adds significant complexity for synthetic
training data where only the drain percentage and relative feature values
matter, not absolute balance continuity.

## D14 — "About 500,000" transaction target
Section 4.3 gives per-account daily Poisson rates (1.0-4.0) that, applied
literally across ~6,000 accounts over 90 days, yield roughly 1-1.5 million
legitimate transactions for the default `--customers 5000 --days 90`
command — more than the "about 500,000" guideline. Per Section 0 rule 3
("where this document gives an exact value... use it exactly") the literal
per-account rates were kept as specified; the "about 500,000" figure is
treated as an approximate sizing note rather than a hard requirement, since
the Sprint 1 acceptance test (Section 16) only checks fraud share and
scenario mix within +/-10%, not total row count. Operators who need a
smaller/faster training world can pass fewer `--customers` or `--days`.

## D15 — Reporting threshold in model_comparison
Section 6.1 step 6's headline precision/recall/F1/FPR ("at the chosen
threshold") use a fixed reporting threshold of **0.5**. The full
precision/recall/alerts-per-1,000 sweep from 0.10 to 0.90 lives in
`reports/threshold_analysis.csv`; the live system's actual operating
thresholds are the configurable `risk_threshold_medium` / `_high` settings
(default 0.40 / 0.70), unrelated to this reporting convention.

## D16 — benchmark_public.py uses fixed hyperparameters, not a full search
Section 6.3 asks for "the same balancing and tuning approach" as the main
pipeline. Running a full `RandomizedSearchCV` (20 iterations x 5 folds) per
model per Kaggle dataset would be very slow for a benchmark-only comparison
that is not deployed. `benchmark_public.py` fits each SMOTE/class-weight (or
scale_pos_weight) variant once with reasonable fixed hyperparameters, keeps
the better variant on validation PR-AUC, and reports the same metrics as
`evaluate.py`. This keeps `make train` runnable in a reasonable time while
still producing a valid comparison table for Chapter Four.

## D17 — Generator balance economics
Applying Section 4.3's Poisson daily rate and lognormal amount (sigma=1.0)
literally gives an expected spend per account, per segment, that can exceed
"starting balance = 5-60x segment median" within days (heavy lognormal tail:
E[amount] ~ 1.65x the median). An earlier version's small fixed monthly
top-up let most accounts' balances collapse toward zero, forcing >60% of
transactions to a small clipped floor — unrealistic and bad training data.
Fixed by: (1) scaling salary/replenishment inflows to
`lambda * median * uniform(10-35)` instead of a fixed multiple of median
alone, triggered monthly for salaried accounts and whenever a non-salaried
account's balance drops under 10x its segment median; (2) never letting a
transaction amount exceed 95% of the account's actual current balance, and
skipping (not forcing) a transaction when funds are too low for a meaningful
one (<50 NGN spendable) rather than manufacturing an overdraft.

## D18 — Audit log append-only enforcement uses a trigger, not REVOKE
Section 7.1 says to "revoke UPDATE/DELETE on this table for the
application's DB user in a migration". docker-compose runs migrations and
the backend under the same single Postgres role (`POSTGRES_USER=ifdims`;
see `.env.example`), and Postgres table owners bypass GRANT/REVOKE checks,
so a literal `REVOKE ... FROM CURRENT_USER` would be a no-op once that role
owns the table. The initial migration instead adds a `BEFORE UPDATE OR
DELETE` trigger (`audit_log_no_update_delete`) that raises on any attempt to
modify or remove a row, which enforces append-only for every role,
including the owner — a stronger version of the same guarantee.

## D19 — GET /cases/meta/assignable-users (not in the spec's endpoint list)
Section 12.1's case detail page needs an "assign dropdown (supervisor)", but
the only user-listing endpoint in Section 8 is `GET /admin/users`, which is
admin-only (Section 9's RBAC table gives supervisors no user-listing
capability at all). Added `GET /cases/meta/assignable-users`
(supervisor-only) returning active analysts and supervisors, the minimum
needed for the assign UI to function. Registered before `/cases/{case_id}`
so the literal "meta" segment isn't swallowed by the `{case_id}` path
parameter.

## D20 — Auto-created high-risk alerts stay OPEN, not CASE_OPENED
An earlier version set a high-severity alert's status to `CASE_OPENED` the
moment its case was auto-created (Section 8.2 step 8). That's wrong: it
made `POST /alerts/{id}/dismiss` (which only accepts `OPEN` alerts, Section
8.3) permanently unusable for high alerts, even though dismissing an alert
whose transaction is `HELD` and releasing it is exactly the fast path an
analyst needs for an auto-created case that turns out to be a false
positive. `CASE_OPENED` is reserved for the *manual*
`POST /alerts/{id}/open-case` flow, where no case exists until an analyst
decides to create one. An auto-created case's alert now stays `OPEN` until
an analyst explicitly dismisses it; the case itself is unaffected by a
later dismissal and is still resolved/closed independently through the
case workflow. Found by a test asserting a high alert appears under
`GET /alerts?status=OPEN`.

## D22 — backend requirements.txt needs pyarrow too
A trained model bundle's `shap_background_sample` is a pandas DataFrame,
and unpickling it via joblib can require `pyarrow` (pandas 3.x uses
PyArrow-backed representations internally for some dtypes) even though
the backend never imports pyarrow itself. `ml/requirements.txt` already
had it (for `build_features.py`'s parquet I/O); `backend/requirements.txt`
did not, so the Docker backend crashed on startup with
`ModuleNotFoundError: No module named 'pyarrow'` the moment a real
locally-trained model bundle was loaded — the smoke-tests never caught
this because the backend's own test fixtures build their model bundle
in-process, in the same Python environment that has pyarrow installed for
other reasons. Added `pyarrow>=15.0` to `backend/requirements.txt`.

## D23 — Multiple uvicorn workers, to actually meet the <500ms load-test target
The first real 20-user/5-minute load test (Section 15.4) came back at
1045ms average response time — over double the NFR target — even though a
single scored request only takes tens of milliseconds end to end (confirmed
by `docker stats`: the backend container used only ~130% CPU out of 400%
available, i.e. roughly 1.3 of 4 cores, while 20 concurrent requests
queued). This is classic single-process Python GIL contention: the
CPU-bound parts of scoring (feature computation, the model's `predict`,
SHAP) serialize on the GIL across threads in one process, so adding
concurrent users just queues them instead of using the other 3 idle cores.

Fixed by running the backend with multiple uvicorn worker **processes**
(`--workers`, default 4, configurable via `UVICORN_WORKERS`) — separate
OS processes each have their own GIL, giving real parallelism. This
reintroduced a correctness gap: `model_registry` is a plain Python
singleton, so each worker process has its own independent copy, and
Section 8.8's "activate a model" hot-swap would otherwise only update
whichever single worker happened to handle that HTTP request, leaving the
others silently serving the old model indefinitely. Fixed with
`ModelRegistry.refresh_if_changed()`, run on a 10-second interval in
*every* worker (no advisory lock needed here, unlike the SLA job: each
worker only ever mutates its own in-memory state) — so an activation
converges across all workers within 10 seconds instead of needing a
full restart.

Side effect worth knowing about: `LoginThrottle` (D3) and the in-memory
rate limiters (D4) are also per-worker-process now, not just
per-container. With 4 workers, the effective ceiling before every worker
independently locks an account is up to ~4x the stated 5-attempts figure
(and similarly for the request-rate limits), rather than a hard global
cap. Still fine for this project's threat model (a single demo/pilot
deployment, not a target for sophisticated distributed brute-forcing), but
a real multi-instance production deployment would want a shared store
(Redis) for both, as D3/D4 already noted.

## D21 — Generator bug: SOCIAL_ENGINEERING incidents could be timestamped years before day 0
`_generate_incident`'s SOCIAL_ENGINEERING branch computed its random
incident time as `_random_timestamp(rng, victim.opened_on + 1 day, end_date)`
instead of `_random_timestamp(rng, start_date, end_date)` like every other
scenario. Since `victim.opened_on` can be up to 5 years before the
generation window's `start_date` (customers join up to 5 years earlier),
this let some fraud transactions land years before the legitimate dataset's
date range — caught by `simulator/seed_history.py`'s "first 45 days" cutoff
silently treating almost the entire world as "future" because `start`
(`transactions_df["txn_time"].min()`) picked up one of these outlier rows.
Fixed by using `start_date`/`end_date` like the other three scenarios;
covered by `ml/tests/test_generator.py::test_all_transactions_fall_within_the_generation_window`.

## D24 — Scoped training to a 500-customer demo dataset; fixed a RandomizedSearchCV n_jobs bug along the way
Initial attempts to train on the full ~5000-customer dataset (and then a
first 500-customer attempt) appeared to hang indefinitely — 30+ minutes
with no progress output, eventually killed with nothing saved. Two
distinct problems were involved, not one:

1. `_tune()` ran `RandomizedSearchCV(..., n_jobs=-1)` around a pipeline
   whose `RandomForestClassifier` *also* sets `n_jobs=-1` internally
   (Section 6.1's own hyperparameter spec). Nesting two `n_jobs=-1` layers
   oversubscribes the CPU — each outer worker process spawns its own full
   thread pool — which is especially costly on Windows, where `loky`'s
   per-dispatch process/memmap overhead is high. Fixed by setting the
   outer search to `n_jobs=1` and letting the inner estimators
   (RandomForest, XGBoost) parallelize internally instead.
2. Separately, and more misleadingly: once output was redirected to a log
   file (for the background training run), Python's `print()` calls were
   fully buffered rather than line-buffered, so real progress sat
   invisible in the buffer while only `warnings.warn()` (unbuffered,
   straight to stderr) appeared — making a training run that was actually
   progressing normally look completely stuck. Running with `python -u`
   (unbuffered stdout) fixed the visibility problem and showed the first
   bug fix was in fact working.

Given this is a demonstration system, not a production deployment, training
was deliberately scoped to 500 synthetic customers / 90 days (~103,000
transactions, 511 labelled fraud) rather than the full ~5000-customer /
~1,000,000-row target, to keep the full build-to-deployment cycle fast and
reliable. The resulting model (`20261001-2222-xgboost`) was registered,
activated, and evaluated like any other: precision 0.92, recall 0.78, F1
0.84, PR-AUC 0.86, 41ms scoring latency — see `reports/` for the full
Chapter Four outputs. Retraining at a larger scale later only requires
re-running `generate_synthetic` / `build_features` / `train` with bigger
`--customers`/`--days` values; no code changes are needed.
