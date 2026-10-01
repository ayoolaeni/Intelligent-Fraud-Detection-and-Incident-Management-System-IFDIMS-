# IFDIMS — Intelligent Fraud Detection and Incident Management System

A near-real-time transaction fraud scoring and incident-management system
for commercial banks: transactions are scored by a trained ML model,
explained with SHAP, banded into low/medium/high risk, and — for high-risk
transactions — held and turned into an incident case that fraud analysts
and supervisors work through a defined workflow. Every action is audited.

Built to the specification in `IFDIMS_Build_Specification.md`. See
`docs/DECISIONS.md` for every place this build made an explicit choice
where the specification was silent.

## Quick start

Prerequisites: Docker, Docker Compose, Python 3.11 (for running the data/
training pipeline and simulator locally), Node 20.

```bash
cp .env.example .env          # edit secrets before any real deployment
make demo                     # up + data + train + seed-demo + stream
```

`make demo` will:
1. Start Postgres, the backend and the frontend (`docker compose up --build`).
2. Generate the synthetic training and demo worlds and build the feature table.
3. Train, evaluate and register (and activate) the fraud model.
4. Load the demo world's first 45 days into the database as history.
5. Stream the remaining transactions to the live scoring API so alerts and
   cases fill up in real time.

Then open **http://localhost:5173** and log in as:

| Role | Email | Password |
|---|---|---|
| Analyst | `analyst1@ifdims.local` | `Demo12345!` |
| Analyst | `analyst2@ifdims.local` | `Demo12345!` |
| Supervisor | `supervisor@ifdims.local` | `Demo12345!` |
| Admin | value of `ADMIN_EMAIL` in `.env` | value of `ADMIN_PASSWORD` in `.env` |

## Individual commands

See the `Makefile` for the full list; the ones you'll use most:

| Command | What it does |
|---|---|
| `make up` / `make down` | Start/stop the Docker stack |
| `make data` | Generate synthetic train + demo worlds, build features |
| `make train` | Train, evaluate, benchmark and register + activate the best model |
| `make seed-demo` | Load the demo world's first 45 days into the database |
| `make stream` | Stream the rest of the demo world to the live API |
| `make test` | Run backend, ML and frontend test suites |
| `make loadtest` | Run the Locust load test and summarise it |
| `make uat-summary` | Summarise collected UAT questionnaire responses |

## Repository structure

```
backend/    FastAPI application (API, services, DB models, migrations, tests)
ml/         fraud_core (shared feature definitions) + training/evaluation pipeline + synthetic generator
frontend/   React + TypeScript + Vite dashboard
simulator/  Loads demo history and streams live transactions to the API
loadtest/   Locust load test
scripts/    Misc utilities (UAT summary)
docs/       Decisions log, user guide, UAT materials, sprint notes
data/       Generated synthetic data and feature tables (git-ignored)
models/     Trained model bundles (git-ignored)
reports/    Evaluation and test outputs for Chapter Four (git-ignored)
```

Each of `backend/`, `ml/`, `frontend/` and `simulator/` has its own short
README with setup notes specific to that part.

## Testing

- `cd ml && pytest` — feature unit tests, generator reproducibility, the
  in-memory batch/online parity check.
- `cd backend && pytest` — API integration tests (auth, scoring, the full
  case workflow, admin, reports) plus the mandatory database-backed feature
  parity test (`tests/test_feature_parity.py`, Section 15.2).
- `cd frontend && npm test` — component tests (login form, role-based menu,
  SHAP chart, case action buttons, formatters).

## Security notes

All personal data in this project is synthetic. BVNs and phone numbers are
never stored in the clear — only salted SHA-256 hashes, per
`docs/DECISIONS.md`. Change every secret in `.env` before any deployment
beyond a local demo.
