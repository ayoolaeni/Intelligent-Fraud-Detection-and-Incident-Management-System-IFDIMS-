"""Constants shared by the training pipeline and the live scoring service.

Everything here is normative: column order, enum values and human-readable
labels used in SHAP explanations and the UI. See Section 5 of
``IFDIMS_Build_Specification.md``.
"""
from __future__ import annotations

# --- Enumerations (Section 4.2) -------------------------------------------------

CHANNELS: list[str] = ["NIP", "MOBILE", "USSD", "INTERNET", "POS", "ATM"]

TXN_TYPES: list[str] = ["TRANSFER", "CARD_PAYMENT", "WITHDRAWAL", "BILL_PAYMENT", "AIRTIME"]

SECURITY_EVENT_TYPES: list[str] = [
    "SIM_SWAP",
    "PIN_RESET",
    "PASSWORD_RESET",
    "NEW_DEVICE_ENROLLED",
]

FRAUD_TYPES: list[str] = [
    "SOCIAL_ENGINEERING",
    "ACCOUNT_TAKEOVER",
    "SIM_SWAP",
    "CARD_FRAUD",
    "INSIDER",
    "IDENTITY_FRAUD",
    "OTHER",
]

# Caps and window sizes used by feature definitions (Section 5).
GLOBAL_LEGIT_AMOUNT_CAP = 20_000_000.0
AMOUNT_TO_AVG_CAP = 100.0
MINS_SINCE_LAST_TXN_CAP = 43_200.0  # 30 days, in minutes
BALANCE_RATIO_CAP = 1.0
ROLLING_WINDOW_DAYS = 30
SECURITY_EVENT_WINDOW_HOURS = 48

TIMEZONE = "Africa/Lagos"

# --- Feature column order (Section 5, Table 3.2) --------------------------------
# 23 columns total, in this exact order. The trained model stores this list and
# scoring must refuse to run if the active model's feature list differs.

FEATURE_NAMES: list[str] = [
    "log_amount",
    "amount_to_avg_30d",
    "hour_sin",
    "hour_cos",
    "is_night",
    "day_of_week",
    "channel_NIP",
    "channel_MOBILE",
    "channel_USSD",
    "channel_INTERNET",
    "channel_POS",
    "channel_ATM",
    "txn_count_1h",
    "txn_count_24h",
    "txn_sum_1h",
    "txn_sum_24h",
    "mins_since_last_txn",
    "is_new_device",
    "is_new_beneficiary",
    "is_location_change",
    "recent_security_event_48h",
    "account_age_days",
    "balance_ratio",
]

assert len(FEATURE_NAMES) == 23, "FEATURE_NAMES must have exactly 23 columns"

FEATURE_LABELS: dict[str, str] = {
    "log_amount": "Transaction amount",
    "amount_to_avg_30d": "Amount compared with 30-day average",
    "hour_sin": "Time of day",
    "hour_cos": "Time of day",
    "is_night": "Night-time transaction",
    "day_of_week": "Day of week",
    "channel_NIP": "Channel: NIP transfer",
    "channel_MOBILE": "Channel: mobile app",
    "channel_USSD": "Channel: USSD",
    "channel_INTERNET": "Channel: internet banking",
    "channel_POS": "Channel: POS",
    "channel_ATM": "Channel: ATM",
    "txn_count_1h": "Transactions in last hour",
    "txn_count_24h": "Transactions in last 24 hours",
    "txn_sum_1h": "Value moved in last hour",
    "txn_sum_24h": "Value moved in last 24 hours",
    "mins_since_last_txn": "Time since previous transaction",
    "is_new_device": "New device",
    "is_new_beneficiary": "New beneficiary",
    "is_location_change": "Unusual location",
    "recent_security_event_48h": "SIM/PIN/password change in last 48 hours",
    "account_age_days": "Account age",
    "balance_ratio": "Share of balance moved",
    # Synthetic label used after merging hour_sin/hour_cos SHAP contributions
    # (fraud_core.features.merge_hour_factors); not one of the 23 model columns.
    "hour_of_day": "Time of day",
}

DAY_NAMES: list[str] = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
