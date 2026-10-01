# Sprint 5 — Users can monitor and report (US10-US13)

## Built

- Auth: `POST /auth/login` (JWT, 60min expiry, 5-attempts/15min lockout,
  5/min rate limit), `/auth/me`, `/auth/change-password`.
- Dashboard: `GET /dashboard/summary`, `GET /dashboard/trends`.
- Reports: cases/alerts/fraud-summary (CSV or PDF, with a matplotlib bar
  chart embedded via reportlab)/nibss-incidents.
- Admin: users (create/update/deactivate-unassigns-cases/reset-password),
  settings (validated `0 < medium < high < 1`), models (list + activate
  with a hot-swap and pre-flight smoke test), audit logs, label export for
  retraining.
- `app/seed.py`: idempotent roles/admin/demo users/default settings.
- Frontend: every page in Section 12.1 — login, overview (KPIs + Recharts
  trend/channel charts), alert queue and detail (with the SHAP bar chart),
  case list/new/detail (action buttons generated from `allowed_transitions`,
  assign modal, notes/attachments/history tabs, release/decline),
  transactions list/detail, reports, all four admin pages, account,
  not-found/forbidden. Role-based `ProtectedRoute` and a sidebar that only
  shows permitted items — the backend remains the authority.

## Note: one endpoint added beyond the spec's list

`GET /cases/meta/assignable-users` (supervisor-only) — the spec gives no
endpoint a supervisor can call to list users for the "assign" dropdown
(`/admin/users` is admin-only). See `docs/DECISIONS.md` D19.

## Tests

`backend/tests/test_auth.py` (6), `test_admin.py` (6): login success/
failure/lockout, role forbidden, password-strength validation, user
creation/duplicate-email, self-deactivation blocked, deactivation
unassigning open cases, settings validation and live effect on the next
scored transaction's band, invalid model activation rejected without
touching `is_active`. `frontend/src/tests/`: login form, role-based menu
visibility, SHAP chart rendering, case action buttons following
`allowed_transitions`, money/date formatters (13 tests, all passing;
`npx tsc --noEmit` also clean).

**Done-when check**: each role can log in and complete its tasks in the
browser; forbidden actions are hidden in the UI (role-filtered nav, guarded
routes) and rejected by the API (verified in tests, not just hidden).
