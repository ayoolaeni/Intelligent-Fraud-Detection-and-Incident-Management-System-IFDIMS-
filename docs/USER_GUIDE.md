# IFDIMS User Guide

## Signing in

Go to the dashboard URL and sign in with the email and password your admin
gave you. After 5 failed attempts in 15 minutes, the account locks for 15
minutes.

## Fraud Analyst

- **Overview**: your landing page. KPI cards, a 30-day trend of alerts and
  confirmed fraud, and a list of cases that are due soon or breaching SLA.
- **Alerts**: transactions the system flagged as medium or high risk.
  Click one to see the transaction, the customer, and the factors that drove
  the score (red bars increase risk, blue bars decrease it — each has a
  plain-English description). From there you can **dismiss** a false
  positive (with a reason) or, for a medium alert, **open a case**.
- **Cases**: incidents assigned to you or unassigned. Open one to see its
  SLA countdown, linked transaction and explanation, notes, and
  attachments. The buttons shown (e.g. "Under investigation", "Escalated",
  "Resolved") are exactly the transitions you're allowed to make right now
  — the system enforces the rest. Resolving a case asks for an outcome
  (confirmed fraud / false positive), and, if confirmed, a fraud type.
- **Transactions**: every scored transaction, searchable by account,
  channel or status.

## Supervisor

Everything an analyst can do, plus:

- **Assign / reassign** a case to any active analyst or supervisor, from
  the case detail page.
- **Approve closure** of a resolved case, **reject** a resolution to send
  it back to investigation, or **reopen** a closed case.
- **Reports**: download case, alert, fraud summary (CSV or PDF) and NIBSS
  incident reports for a date range and channel.

## Administrator

- **Users**: create accounts, change roles, deactivate/reactivate, reset
  passwords. Deactivating a user unassigns their open cases (they go back
  to "New" with a system note).
- **Settings**: the medium/high risk thresholds (the model page shows what
  it suggests, based on validation-set precision/recall), the critical
  transaction amount, SLA times per priority, and whether high-risk
  transactions are held and new high-risk cases auto-assigned.
- **Models**: every trained model version with its test-set metrics.
  Activating one runs a smoke prediction first; if that fails, nothing
  changes.
- **Audit log**: every login and every state-changing action, searchable
  and with full JSON detail.

## Money, times and masking

Amounts are shown as `₦1,250,000.00`. Times are shown in Africa/Lagos
time. Account numbers and phone numbers are masked (e.g. `******6789`,
`****1234`) everywhere in the UI; the backend never sends the full value.
