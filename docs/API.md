# IFDIMS API

The full, always-current contract is the generated OpenAPI schema, served
by the running backend at `/docs` (Swagger UI) and `/openapi.json`. This
document gives the shape of the handful of endpoints worth seeing an
example of; see `IFDIMS_Build_Specification.md` Section 8 for the complete
endpoint list and their exact request/response fields.

All endpoints are under `/api/v1` except `/health`. Errors always look
like `{"detail": "human-readable message", "code": "MACHINE_READABLE_CODE"}`.

## Authenticating

```
POST /api/v1/auth/login
{"email": "analyst1@ifdims.local", "password": "Demo12345!"}

-> 200
{"access_token": "...", "token_type": "bearer", "expires_in": 3600,
 "user": {"user_id": "...", "full_name": "...", "email": "...", "role": "analyst"}}
```

Send the token as `Authorization: Bearer <access_token>` on every
subsequent request. The Transaction System instead authenticates with an
`X-API-Key` header (see `SERVICE_API_KEYS` in `.env`).

## Scoring a transaction

```
POST /api/v1/transactions/score
X-API-Key: sim-key-change-me
{
  "txn_ref": "NIP-20261015-000123", "account_number": "0123456789",
  "amount": "250000.00", "channel": "NIP", "txn_type": "TRANSFER",
  "txn_time": "2026-10-15T21:42:10+01:00", "beneficiary_account": "9876543210",
  "beneficiary_bank": "058", "device_id": "dev-7f3a", "location": "Lagos",
  "balance_before": "310000.00"
}

-> 200
{
  "txn_id": "...", "prediction_id": "...", "fraud_score": 0.8731,
  "risk_band": "high", "decision": "HOLD", "alert_id": "...", "case_id": "...",
  "case_number": "FC-2026-000123",
  "top_factors": [{"feature": "is_new_beneficiary", "label": "New beneficiary",
                    "raw_value": 1, "contribution": 0.412,
                    "description": "Beneficiary has never been paid before"}],
  "model_version": "20261015-1430-xgboost", "latency_ms": 38.5
}
```

Resubmitting the same `txn_ref` returns the same result (idempotent).
`503 NO_ACTIVE_MODEL` if no model version is currently active.

## Working a case

```
GET  /api/v1/cases/{id}                     -> case, notes, attachments, allowed_transitions
POST /api/v1/cases/{id}/assign              {"user_id": "..."}                (supervisor)
POST /api/v1/cases/{id}/transition          {"to_status": "RESOLVED", "note": "...",
                                              "outcome": "confirmed_fraud",
                                              "fraud_type": "SOCIAL_ENGINEERING"}
```

`allowed_transitions` in the case detail response is generated from the
same state-machine table the backend enforces
(`backend/app/services/case_service.py:TRANSITIONS`), so the UI never shows
a button the API would reject.
