"""Unit tests for fraud_core.features (Section 15.1) and the online/batch
parity guarantee (Section 15.2, exercised here in miniature; the full
database-backed parity test lives in backend/tests/test_feature_parity.py).
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from fraud_core.constants import FEATURE_NAMES, MINS_SINCE_LAST_TXN_CAP
from fraud_core.features import (
    compute_features_batch,
    compute_features_online,
    describe_factor,
    merge_hour_factors,
    risk_band,
)

LAGOS = ZoneInfo("Africa/Lagos")


def _dt(y, m, d, h=12, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=LAGOS)


# --------------------------------------------------------------------------- #
# Risk band boundaries (Section 15.1)
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "score,expected",
    [(0.3999, "low"), (0.40, "medium"), (0.70, "medium"), (0.7001, "high")],
)
def test_risk_band_boundaries(score, expected):
    assert risk_band(score, medium_threshold=0.40, high_threshold=0.70) == expected


# --------------------------------------------------------------------------- #
# compute_features_online — edge cases
# --------------------------------------------------------------------------- #

def _base_txn(**overrides):
    txn = dict(
        amount=1000.0,
        channel="MOBILE",
        txn_type="TRANSFER",
        txn_time=_dt(2026, 1, 15, 12, 0),
        beneficiary_account="9990001111",
        device_id="dev-1",
        location="Lagos",
        balance_before=50000.0,
    )
    txn.update(overrides)
    return txn


def test_no_history_defaults():
    account = {"opened_on": date(2020, 1, 1)}
    feats = compute_features_online(_base_txn(), [], [], account, global_median=2000.0)
    assert feats["txn_count_1h"] == 0
    assert feats["txn_count_24h"] == 0
    assert feats["mins_since_last_txn"] == MINS_SINCE_LAST_TXN_CAP
    assert feats["is_new_device"] == 1
    assert feats["is_new_beneficiary"] == 1
    assert feats["is_location_change"] == 0
    assert math.isclose(feats["amount_to_avg_30d"], 1000.0 / 2000.0)


def test_zero_balance_caps_ratio_at_one():
    account = {"opened_on": date(2020, 1, 1)}
    feats = compute_features_online(_base_txn(balance_before=0), [], [], account, global_median=2000.0)
    assert feats["balance_ratio"] == 1.0


def test_non_transfer_never_flags_new_beneficiary():
    account = {"opened_on": date(2020, 1, 1)}
    txn = _base_txn(txn_type="CARD_PAYMENT", beneficiary_account=None)
    feats = compute_features_online(txn, [], [], account, global_median=2000.0)
    assert feats["is_new_beneficiary"] == 0


def test_midnight_is_night():
    account = {"opened_on": date(2020, 1, 1)}
    txn = _base_txn(txn_time=_dt(2026, 1, 15, 0, 30))
    feats = compute_features_online(txn, [], [], account, global_median=2000.0)
    assert feats["is_night"] == 1
    assert feats["hour_sin"] == pytest.approx(math.sin(2 * math.pi * 0 / 24))


def test_known_device_and_beneficiary_from_history():
    account = {"opened_on": date(2020, 1, 1)}
    history = [
        {
            "txn_time": _dt(2026, 1, 15, 9, 0),
            "amount": 500.0,
            "location": "Lagos",
            "device_id": "dev-1",
            "beneficiary_account": "9990001111",
        }
    ]
    feats = compute_features_online(_base_txn(), history, [], account, global_median=2000.0)
    assert feats["is_new_device"] == 0
    assert feats["is_new_beneficiary"] == 0
    assert feats["txn_count_24h"] == 1


def test_recent_security_event_flag():
    account = {"opened_on": date(2020, 1, 1)}
    events = [{"event_time": _dt(2026, 1, 15, 10, 0)}]  # 2h before txn
    feats = compute_features_online(_base_txn(), [], events, account, global_median=2000.0)
    assert feats["recent_security_event_48h"] == 1

    old_events = [{"event_time": _dt(2026, 1, 1, 10, 0)}]  # way outside window
    feats2 = compute_features_online(_base_txn(), [], old_events, account, global_median=2000.0)
    assert feats2["recent_security_event_48h"] == 0


def test_amount_to_avg_cap():
    account = {"opened_on": date(2020, 1, 1)}
    history = [
        {
            "txn_time": _dt(2026, 1, 14, 9, 0),
            "amount": 1.0,
            "location": "Lagos",
            "device_id": "dev-1",
            "beneficiary_account": None,
        }
    ]
    feats = compute_features_online(_base_txn(amount=10_000.0), history, [], account, global_median=2000.0)
    assert feats["amount_to_avg_30d"] == 100.0


# --------------------------------------------------------------------------- #
# describe_factor / merge_hour_factors
# --------------------------------------------------------------------------- #

def test_describe_factor_examples():
    assert "30-day average" in describe_factor("amount_to_avg_30d", 12.4)
    assert describe_factor("is_new_beneficiary", 1) == "Beneficiary has never been paid before"
    assert "SIM swap" in describe_factor("recent_security_event_48h", 1)
    assert describe_factor("txn_count_1h", 5) == "5 transactions in the last hour"


@pytest.mark.parametrize(
    "feature,raw_value,expected_substring",
    [
        ("log_amount", math.log1p(5000), "Transaction amount is"),
        ("hour_of_day", 14, "Time of day (14:00)"),
        ("is_night", 0, "Daytime transaction"),
        ("is_night", 1, "Night-time transaction"),
        ("day_of_week", 0, "Monday"),
        ("day_of_week", 6, "Sunday"),
        ("channel_NIP", 1, "Channel used: NIP"),
        ("channel_NIP", 0, "Not a NIP transaction"),
        ("txn_count_24h", 1, "1 transaction in the last 24 hours"),
        ("txn_sum_1h", math.log1p(2000), "moved in the last hour"),
        ("txn_sum_24h", math.log1p(2000), "moved in the last 24 hours"),
        ("mins_since_last_txn", MINS_SINCE_LAST_TXN_CAP, "No transaction in the last 30 days"),
        ("mins_since_last_txn", 30, "minutes since the previous transaction"),
        ("mins_since_last_txn", 120, "hours since the previous transaction"),
        ("is_new_device", 0, "Transaction made from a known device"),
        ("is_new_device", 1, "new, previously unseen device"),
        ("is_new_beneficiary", 0, "has been paid before"),
        ("is_location_change", 1, "unusual for this account"),
        ("is_location_change", 0, "matches the account's usual pattern"),
        ("recent_security_event_48h", 0, "No SIM/PIN/password change"),
        ("account_age_days", 10, "only 10 days old"),
        ("account_age_days", 400, "400 days old"),
        ("balance_ratio", 0.5, "50% of the available balance"),
        ("some_unknown_feature", 42, "42"),
    ],
)
def test_describe_factor_all_branches(feature, raw_value, expected_substring):
    assert expected_substring in describe_factor(feature, raw_value)


def test_merge_hour_factors_combines_sin_cos():
    items = [
        {"feature": "hour_sin", "raw_value": 0.5, "contribution": 0.1},
        {"feature": "is_new_device", "raw_value": 1, "contribution": 0.2},
        {"feature": "hour_cos", "raw_value": 0.8, "contribution": 0.05},
    ]
    merged = merge_hour_factors(items, hour=14)
    features = [m["feature"] for m in merged]
    assert "hour_sin" not in features and "hour_cos" not in features
    assert "hour_of_day" in features
    hod = next(m for m in merged if m["feature"] == "hour_of_day")
    assert hod["contribution"] == pytest.approx(0.15)
    assert hod["raw_value"] == 14


# --------------------------------------------------------------------------- #
# Batch vs online parity on a small synthetic scenario
# --------------------------------------------------------------------------- #

def test_batch_matches_online_small_scenario():
    account_number = "0000000001"
    opened_on = date(2025, 1, 1)
    accounts_df = pd.DataFrame([{"account_number": account_number, "opened_on": opened_on}])

    rows = []
    base = datetime(2026, 1, 1, 8, 0, tzinfo=LAGOS)
    for i in range(6):
        rows.append({
            "txn_ref": f"T{i}",
            "account_number": account_number,
            "amount": 1000.0 * (i + 1),
            "channel": "MOBILE",
            "txn_type": "TRANSFER",
            "txn_time": base + timedelta(hours=i * 5),
            "beneficiary_account": "BEN1" if i % 2 == 0 else "BEN2",
            "device_id": "dev-1" if i < 4 else "dev-2",
            "location": "Lagos" if i != 3 else "Abuja",
            "balance_before": 100000.0,
        })
    transactions_df = pd.DataFrame(rows)
    security_events_df = pd.DataFrame(columns=["account_number", "event_type", "event_time"])

    global_median = 1500.0
    batch_result = compute_features_batch(transactions_df, security_events_df, accounts_df, global_median)

    # Now recompute each row independently via the online path, using only
    # "history" (earlier rows) as a human would query the database.
    for i, row in transactions_df.iterrows():
        history = []
        for j in range(i):
            h = transactions_df.iloc[j]
            if row["txn_time"] - h["txn_time"] <= timedelta(days=30):
                history.append({
                    "txn_time": h["txn_time"],
                    "amount": h["amount"],
                    "location": h["location"],
                    "device_id": h["device_id"],
                    "beneficiary_account": h["beneficiary_account"],
                })
        seen_devices = {transactions_df.iloc[j]["device_id"] for j in range(i)}
        seen_benefs = {transactions_df.iloc[j]["beneficiary_account"] for j in range(i)}
        txn = {
            "amount": row["amount"],
            "channel": row["channel"],
            "txn_type": row["txn_type"],
            "txn_time": row["txn_time"],
            "beneficiary_account": row["beneficiary_account"],
            "device_id": row["device_id"],
            "location": row["location"],
            "balance_before": row["balance_before"],
        }
        online_feats = compute_features_online(
            txn, history, [], {"opened_on": opened_on}, global_median,
            device_seen_before=row["device_id"] in seen_devices,
            beneficiary_seen_before=row["beneficiary_account"] in seen_benefs,
        )
        batch_feats = batch_result.iloc[i]
        for name in FEATURE_NAMES:
            assert online_feats[name] == pytest.approx(float(batch_feats[name]), abs=1e-6), (
                f"mismatch on row {i}, feature {name}: "
                f"online={online_feats[name]} batch={batch_feats[name]}"
            )
