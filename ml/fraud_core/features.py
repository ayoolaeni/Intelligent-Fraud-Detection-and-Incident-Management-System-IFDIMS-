"""The single source of truth for feature engineering (Section 5 of the spec).

Two entry points are provided and MUST produce identical values for the same
transaction and history (proved by the parity test, Section 15.2):

- ``compute_features_online``  — used by the backend for one transaction at a
  time, given history already loaded from the database (Section 7.4).
- ``compute_features_batch``   — used by the training pipeline over a whole
  transactions table.

Both delegate to the private ``_compute_from_primitives`` function so the
actual arithmetic is written exactly once.
"""
from __future__ import annotations

import math
from collections import Counter, deque
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

from fraud_core.constants import (
    AMOUNT_TO_AVG_CAP,
    BALANCE_RATIO_CAP,
    CHANNELS,
    DAY_NAMES,
    FEATURE_LABELS,
    FEATURE_NAMES,
    MINS_SINCE_LAST_TXN_CAP,
    ROLLING_WINDOW_DAYS,
    SECURITY_EVENT_WINDOW_HOURS,
    TIMEZONE,
)

LAGOS_TZ = ZoneInfo(TIMEZONE)


# --------------------------------------------------------------------------- #
# Small shared helpers
# --------------------------------------------------------------------------- #

def _localize(dt: datetime) -> datetime:
    """Return ``dt`` as a timezone-aware datetime in Africa/Lagos.

    Naive datetimes are assumed to already represent Africa/Lagos local time
    (this is how the synthetic generator and the database both store times).
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=LAGOS_TZ)
    return dt.astimezone(LAGOS_TZ)


def _to_date(value) -> date:
    if isinstance(value, datetime) or isinstance(value, pd.Timestamp):
        return value.date()
    if isinstance(value, date):
        return value
    raise TypeError(f"Cannot convert {value!r} of type {type(value)} to a date")


def risk_band(score: float, medium_threshold: float, high_threshold: float) -> str:
    """Map a fraud probability to a risk band using configurable thresholds.

    low < medium_threshold <= medium <= high_threshold < high
    """
    if score > high_threshold:
        return "high"
    if score >= medium_threshold:
        return "medium"
    return "low"


# --------------------------------------------------------------------------- #
# Core arithmetic, shared by both entry points
# --------------------------------------------------------------------------- #

def _compute_from_primitives(
    *,
    amount: float,
    channel: str,
    txn_time: datetime,
    beneficiary_account: str | None,
    txn_type: str,
    device_id: str | None,
    location: str,
    balance_before: float | None,
    history: list[tuple],
    location_counter: Counter,
    device_seen_before: bool,
    beneficiary_seen_before: bool,
    security_events_in_window: list,
    account_opened_on,
    global_median: float,
) -> dict:
    """``history`` is a list of ``(time, amount, location, device_id,
    beneficiary_account)`` tuples for the account, strictly before ``txn_time``
    and within the last :data:`ROLLING_WINDOW_DAYS` days, sorted ascending by
    time. ``location_counter`` counts locations over that same window.
    """
    T = _localize(txn_time)
    amount = float(amount)

    log_amount = math.log1p(amount)

    lower_1h = txn_time - timedelta(hours=1)
    lower_24h = txn_time - timedelta(hours=24)
    amounts_1h = [h[1] for h in history if h[0] > lower_1h]
    amounts_24h = [h[1] for h in history if h[0] > lower_24h]

    if history:
        avg_30d = sum(h[1] for h in history) / len(history)
        amount_to_avg = (amount / avg_30d) if avg_30d > 0 else (amount / global_median if global_median else 0.0)
    else:
        amount_to_avg = (amount / global_median) if global_median else 0.0
    amount_to_avg = min(amount_to_avg, AMOUNT_TO_AVG_CAP)

    hour = T.hour
    hour_sin = math.sin(2 * math.pi * hour / 24)
    hour_cos = math.cos(2 * math.pi * hour / 24)
    is_night = 1 if 0 <= hour <= 4 else 0
    day_of_week = T.weekday()

    channel_onehot = {f"channel_{c}": (1 if channel == c else 0) for c in CHANNELS}

    txn_count_1h = len(amounts_1h)
    txn_count_24h = len(amounts_24h)
    txn_sum_1h = math.log1p(sum(amounts_1h))
    txn_sum_24h = math.log1p(sum(amounts_24h))

    if history:
        mins_since_last = (txn_time - history[-1][0]).total_seconds() / 60.0
        mins_since_last = min(max(mins_since_last, 0.0), MINS_SINCE_LAST_TXN_CAP)
    else:
        mins_since_last = MINS_SINCE_LAST_TXN_CAP

    is_new_device = 1 if (device_id is not None and not device_seen_before) else 0
    is_new_beneficiary = 1 if (
        txn_type == "TRANSFER" and beneficiary_account is not None and not beneficiary_seen_before
    ) else 0

    if location_counter:
        most_common_location, _ = location_counter.most_common(1)[0]
        is_location_change = 0 if location == most_common_location else 1
    else:
        is_location_change = 0

    recent_security_event_48h = 1 if len(security_events_in_window) > 0 else 0

    if account_opened_on is not None:
        age_days = float((T.date() - _to_date(account_opened_on)).days)
        age_days = max(age_days, 0.0)
    else:
        age_days = 0.0

    if balance_before is not None and float(balance_before) > 0:
        balance_ratio = min(amount / float(balance_before), BALANCE_RATIO_CAP)
    else:
        balance_ratio = BALANCE_RATIO_CAP

    feats = {
        "log_amount": log_amount,
        "amount_to_avg_30d": amount_to_avg,
        "hour_sin": hour_sin,
        "hour_cos": hour_cos,
        "is_night": is_night,
        "day_of_week": day_of_week,
        **channel_onehot,
        "txn_count_1h": txn_count_1h,
        "txn_count_24h": txn_count_24h,
        "txn_sum_1h": txn_sum_1h,
        "txn_sum_24h": txn_sum_24h,
        "mins_since_last_txn": mins_since_last,
        "is_new_device": is_new_device,
        "is_new_beneficiary": is_new_beneficiary,
        "is_location_change": is_location_change,
        "recent_security_event_48h": recent_security_event_48h,
        "account_age_days": age_days,
        "balance_ratio": balance_ratio,
    }
    return {name: feats[name] for name in FEATURE_NAMES}


# --------------------------------------------------------------------------- #
# Online entry point
# --------------------------------------------------------------------------- #

def compute_features_online(
    txn: dict,
    history_txns: list[dict],
    security_events: list[dict],
    account: dict,
    global_median: float,
    *,
    device_seen_before: bool | None = None,
    beneficiary_seen_before: bool | None = None,
) -> dict:
    """Compute the 23 features for one transaction, backend side.

    Parameters
    ----------
    txn: dict with keys amount, channel, txn_type, txn_time (aware or naive
        Africa/Lagos datetime), beneficiary_account, device_id, location,
        balance_before.
    history_txns: the account's transactions in the last 30 days, strictly
        before ``txn["txn_time"]`` (Section 7.4 query 1). Each item is a dict
        with keys amount, txn_time, location, device_id, beneficiary_account.
    security_events: the account's security events in the last 48 hours,
        up to and including ``txn["txn_time"]`` (Section 7.4 query 4). Each
        item is a dict with key event_time.
    account: dict with key opened_on (date).
    global_median: GLOBAL_MEDIAN_AMOUNT saved with the active model.
    device_seen_before / beneficiary_seen_before: results of the full-history
        EXISTS queries (Section 7.4 queries 2 and 3). When omitted, they are
        derived from ``history_txns`` only, which is correct as long as the
        device/beneficiary would have shown up within the last 30 days too
        (fine for tests and the synthetic generator, but the live backend
        MUST pass these explicitly).
    """
    T = txn["txn_time"]

    history = sorted(
        (
            (
                h["txn_time"],
                float(h["amount"]),
                h["location"],
                h.get("device_id"),
                h.get("beneficiary_account"),
            )
            for h in history_txns
        ),
        key=lambda item: item[0],
    )
    location_counter = Counter(h[2] for h in history)

    if device_seen_before is None:
        device_seen_before = txn.get("device_id") is not None and any(
            h[3] == txn.get("device_id") for h in history
        )
    if beneficiary_seen_before is None:
        beneficiary_seen_before = (
            txn.get("txn_type") == "TRANSFER"
            and txn.get("beneficiary_account") is not None
            and any(h[4] == txn.get("beneficiary_account") for h in history)
        )

    window_start = T - timedelta(hours=SECURITY_EVENT_WINDOW_HOURS)
    sec_in_window = [
        e for e in security_events if window_start <= e["event_time"] <= T
    ]

    return _compute_from_primitives(
        amount=txn["amount"],
        channel=txn["channel"],
        txn_time=T,
        beneficiary_account=txn.get("beneficiary_account"),
        txn_type=txn["txn_type"],
        device_id=txn.get("device_id"),
        location=txn["location"],
        balance_before=txn.get("balance_before"),
        history=history,
        location_counter=location_counter,
        device_seen_before=bool(device_seen_before),
        beneficiary_seen_before=bool(beneficiary_seen_before),
        security_events_in_window=sec_in_window,
        account_opened_on=account["opened_on"],
        global_median=global_median,
    )


# --------------------------------------------------------------------------- #
# Batch entry point
# --------------------------------------------------------------------------- #

def compute_features_batch(
    transactions_df: pd.DataFrame,
    security_events_df: pd.DataFrame,
    accounts_df: pd.DataFrame,
    global_median: float,
) -> pd.DataFrame:
    """Compute the 23 features for every row of ``transactions_df``.

    ``transactions_df`` must have columns: txn_ref, account_number, amount,
    channel, txn_type, txn_time, beneficiary_account, device_id, location,
    balance_before. ``security_events_df`` must have: account_number,
    event_type, event_time. ``accounts_df`` must have: account_number,
    opened_on.

    Returns a DataFrame with column ``txn_ref`` plus the 23 feature columns,
    in the same row order as ``transactions_df``.
    """
    df = transactions_df.copy()
    df["txn_time"] = pd.to_datetime(df["txn_time"], format="ISO8601")
    if df["txn_time"].dt.tz is None:
        df["txn_time"] = df["txn_time"].dt.tz_localize(LAGOS_TZ)
    else:
        df["txn_time"] = df["txn_time"].dt.tz_convert(LAGOS_TZ)
    df = df.sort_values(["account_number", "txn_time"], kind="mergesort").reset_index(drop=True)

    sec = security_events_df.copy()
    if len(sec):
        sec["event_time"] = pd.to_datetime(sec["event_time"], format="ISO8601")
        if sec["event_time"].dt.tz is None:
            sec["event_time"] = sec["event_time"].dt.tz_localize(LAGOS_TZ)
        else:
            sec["event_time"] = sec["event_time"].dt.tz_convert(LAGOS_TZ)
        sec = sec.sort_values(["account_number", "event_time"])
        sec_by_account = {acc: grp["event_time"].tolist() for acc, grp in sec.groupby("account_number")}
    else:
        sec_by_account = {}

    opened_on_by_account = accounts_df.set_index("account_number")["opened_on"].to_dict()

    window_days = pd.Timedelta(days=ROLLING_WINDOW_DAYS)
    sec_window = pd.Timedelta(hours=SECURITY_EVENT_WINDOW_HOURS)

    out_rows: list[dict] = []

    for account_number, group in df.groupby("account_number", sort=False):
        window: deque = deque()  # (time, amount, location, device_id, beneficiary_account)
        seen_devices: set = set()
        seen_beneficiaries: set = set()
        location_counter: Counter = Counter()
        acc_opened = opened_on_by_account.get(account_number)
        ev_times = sec_by_account.get(account_number, [])

        for _, row in group.iterrows():
            T = row["txn_time"]
            lower_30 = T - window_days
            while window and window[0][0] <= lower_30:
                _, _, old_loc, _, _ = window.popleft()
                location_counter[old_loc] -= 1
                if location_counter[old_loc] <= 0:
                    del location_counter[old_loc]

            history = list(window)  # ascending order, strictly < T, within 30 days
            device_id = row.get("device_id")
            beneficiary_account = row.get("beneficiary_account")
            device_id = None if pd.isna(device_id) else device_id
            beneficiary_account = None if pd.isna(beneficiary_account) else beneficiary_account

            device_seen_before = device_id is not None and device_id in seen_devices
            beneficiary_seen_before = (
                row["txn_type"] == "TRANSFER"
                and beneficiary_account is not None
                and beneficiary_account in seen_beneficiaries
            )
            sec_window_start = T - sec_window
            sec_in_window = [t for t in ev_times if sec_window_start <= t <= T]

            feats = _compute_from_primitives(
                amount=row["amount"],
                channel=row["channel"],
                txn_time=T,
                beneficiary_account=beneficiary_account,
                txn_type=row["txn_type"],
                device_id=device_id,
                location=row["location"],
                balance_before=row.get("balance_before"),
                history=history,
                location_counter=location_counter,
                device_seen_before=device_seen_before,
                beneficiary_seen_before=beneficiary_seen_before,
                security_events_in_window=sec_in_window,
                account_opened_on=acc_opened,
                global_median=global_median,
            )
            out_rows.append({"txn_ref": row["txn_ref"], **feats})

            # push current transaction into history for subsequent ones
            window.append((T, float(row["amount"]), row["location"], device_id, beneficiary_account))
            location_counter[row["location"]] += 1
            if device_id is not None:
                seen_devices.add(device_id)
            if row["txn_type"] == "TRANSFER" and beneficiary_account is not None:
                seen_beneficiaries.add(beneficiary_account)

    result = pd.DataFrame(out_rows)
    result = result.set_index("txn_ref").loc[transactions_df["txn_ref"].values].reset_index()
    return result


# --------------------------------------------------------------------------- #
# SHAP explanation helpers
# --------------------------------------------------------------------------- #

def merge_hour_factors(shap_items: list[dict], hour: int) -> list[dict]:
    """Merge ``hour_sin``/``hour_cos`` SHAP entries into one ``hour_of_day``
    entry, summing their contributions. Other entries pass through unchanged,
    in their original relative order.
    """
    merged: list[dict] = []
    hour_index: int | None = None
    hour_contribution = 0.0
    hour_seen = False
    for item in shap_items:
        if item["feature"] in ("hour_sin", "hour_cos"):
            hour_contribution += item["contribution"]
            hour_seen = True
            if hour_index is None:
                hour_index = len(merged)
                merged.append({
                    "feature": "hour_of_day",
                    "raw_value": hour,
                    "contribution": hour_contribution,
                })
            else:
                merged[hour_index]["contribution"] = hour_contribution
            continue
        merged.append(dict(item))
    if hour_seen:
        return merged
    return [dict(item) for item in shap_items]


def describe_factor(feature: str, raw_value) -> str:
    """Return a plain-English sentence describing a factor's raw value."""
    if feature == "log_amount":
        amount = math.expm1(float(raw_value))
        return f"Transaction amount is ₦{amount:,.2f}"
    if feature == "amount_to_avg_30d":
        return f"Amount is {float(raw_value):.1f}× the 30-day average"
    if feature in ("hour_sin", "hour_cos", "hour_of_day"):
        hour = int(round(float(raw_value))) % 24
        return f"Time of day ({hour:02d}:00)"
    if feature == "is_night":
        return "Night-time transaction (00:00–04:59)" if raw_value else "Daytime transaction"
    if feature == "day_of_week":
        idx = int(round(float(raw_value))) % 7
        return f"Day of week: {DAY_NAMES[idx]}"
    if feature.startswith("channel_"):
        chan = feature.split("_", 1)[1]
        return f"Channel used: {chan}" if raw_value else f"Not a {chan} transaction"
    if feature == "txn_count_1h":
        n = int(round(float(raw_value)))
        return f"{n} transaction{'s' if n != 1 else ''} in the last hour"
    if feature == "txn_count_24h":
        n = int(round(float(raw_value)))
        return f"{n} transaction{'s' if n != 1 else ''} in the last 24 hours"
    if feature == "txn_sum_1h":
        amt = math.expm1(float(raw_value))
        return f"₦{amt:,.2f} moved in the last hour"
    if feature == "txn_sum_24h":
        amt = math.expm1(float(raw_value))
        return f"₦{amt:,.2f} moved in the last 24 hours"
    if feature == "mins_since_last_txn":
        mins = float(raw_value)
        if mins >= MINS_SINCE_LAST_TXN_CAP:
            return "No transaction in the last 30 days (or this is the first transaction)"
        if mins < 60:
            return f"{mins:.0f} minutes since the previous transaction"
        return f"{mins / 60:.1f} hours since the previous transaction"
    if feature == "is_new_device":
        return "Transaction made from a new, previously unseen device" if raw_value else "Transaction made from a known device"
    if feature == "is_new_beneficiary":
        return "Beneficiary has never been paid before" if raw_value else "Beneficiary has been paid before"
    if feature == "is_location_change":
        return "Transaction location is unusual for this account" if raw_value else "Transaction location matches the account's usual pattern"
    if feature == "recent_security_event_48h":
        return "SIM swap or credential reset in the last 48 hours" if raw_value else "No SIM/PIN/password change in the last 48 hours"
    if feature == "account_age_days":
        days = float(raw_value)
        if days < 30:
            return f"Account is only {days:.0f} days old"
        return f"Account is {days:.0f} days old"
    if feature == "balance_ratio":
        return f"Transaction uses {float(raw_value) * 100:.0f}% of the available balance"
    label = FEATURE_LABELS.get(feature, feature)
    return f"{label}: {raw_value}"
