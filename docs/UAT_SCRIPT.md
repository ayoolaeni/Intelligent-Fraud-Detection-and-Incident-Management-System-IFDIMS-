# IFDIMS User Acceptance Test Script

Run this after `make demo` so the alert queue and cases have live data.
Give testers the relevant login from Section 14 of the build specification
(e.g. `analyst1@ifdims.local` / `Demo12345!`, `supervisor@ifdims.local` /
`Demo12345!`). Testers fill in `docs/UAT_QUESTIONNAIRE.md` afterwards.

## Tasks

1. **(analyst)** Log in and find the highest-risk open alert. Explain, in
   your own words, why it was flagged, using the listed factors.
2. **(analyst)** Dismiss a medium-severity alert as a false positive, with a
   reason.
3. **(analyst)** Open one of your assigned cases, move it to "under
   investigation", and add a note describing what you checked.
4. **(analyst)** Resolve an assigned case as confirmed fraud, selecting a
   fraud type and (if applicable) an amount recovered.
5. **(analyst)** Escalate a different case to a supervisor with a reason.
6. **(supervisor)** Assign an unassigned critical-priority case to an
   analyst.
7. **(supervisor)** Approve the closure of a resolved case.
8. **(supervisor or admin)** Download the fraud summary report as a PDF
   and check that the numbers look consistent with the dashboard.
