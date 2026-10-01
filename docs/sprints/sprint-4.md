# Sprint 4 — Alerts managed as cases (US5-US9)

## Built

- `app/services/case_service.py`: the full state machine as data
  (`TRANSITIONS`), priority/SLA calculation, `case_number` generation,
  auto-assign to least-loaded analyst, resolution side effects (held
  transaction -> DECLINED/APPROVED, customer risk profile -> high on
  confirmed fraud), reopen (fresh `resolve_due_at`), `allowed_transitions_for`
  (same table the API uses to enforce transitions, so the UI never offers a
  button the backend would reject).
- `app/services/alert_service.py`: dismiss (releases a held transaction),
  open-case-from-medium-alert.
- `app/services/sla_service.py`: single-pass breach check guarded by a
  Postgres advisory lock, run every 60s via APScheduler; a case is
  escalated at most once per breach because it leaves the "active" status
  set as soon as it's escalated.
- `app/services/notification_service.py`, `app/core/audit.py`.
- `POST/GET /cases`, `/cases/{id}/assign|transition|notes|attachments|history`,
  `/alerts`, `/alerts/{id}/dismiss|open-case`.

## Bug found and fixed during this sprint

Resolution side effects only fired `if txn.status == "HELD"`, so
reopening a resolved case and resolving it again with a *different*
outcome (e.g. overturning confirmed_fraud to false_positive) silently left
the transaction in its first-resolution status. Fixed by applying the
outcome unconditionally whenever a case has a linked transaction, since a
case can legitimately be resolved more than once via reopen.

## Tests

`backend/tests/test_case_workflow.py` (3 tests, one exercising the entire
lifecycle): NEW -> assign -> investigate -> escalate -> return -> resolve
(confirmed fraud, verifying `txn.status == DECLINED` and
`customer.risk_profile == "high"`) -> close -> reopen -> resolve (false
positive, verifying `txn.status == APPROVED`) -> close; role checks at each
step (analyst forbidden from assigning or closing); `409 INVALID_TRANSITION`
on an out-of-order move; `409 NO_ASSIGNEE` returning an escalated,
never-assigned case to investigation; alert dismissal releasing a held
transaction.

**Done-when check**: the full workflow integration test passes.
