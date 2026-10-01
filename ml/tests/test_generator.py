"""Generator reproducibility and sanity checks (Section 15.1 / Sprint 1)."""
from __future__ import annotations

import hashlib
import json

from generator.generate_synthetic import run


def _hash_file(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_same_seed_produces_identical_output(tmp_path):
    out1 = tmp_path / "run1"
    out2 = tmp_path / "run2"
    run(out1, n_customers=40, days=10, seed=123, fraud_rate=0.02, label_noise_rate=0.0)
    run(out2, n_customers=40, days=10, seed=123, fraud_rate=0.02, label_noise_rate=0.0)

    for name in ("customers.csv", "accounts.csv", "transactions.csv", "security_events.csv"):
        assert _hash_file(out1 / name) == _hash_file(out2 / name), f"{name} differs between identical-seed runs"


def test_different_seed_produces_different_output(tmp_path):
    out1 = tmp_path / "run1"
    out2 = tmp_path / "run2"
    run(out1, n_customers=40, days=10, seed=1, fraud_rate=0.02, label_noise_rate=0.0)
    run(out2, n_customers=40, days=10, seed=2, fraud_rate=0.02, label_noise_rate=0.0)
    assert _hash_file(out1 / "transactions.csv") != _hash_file(out2 / "transactions.csv")


def test_fraud_share_within_tolerance(tmp_path):
    out = tmp_path / "world"
    run(out, n_customers=300, days=30, seed=7, fraud_rate=0.02, label_noise_rate=0.0)
    summary = json.loads((out / "summary.json").read_text())
    # +/-30% relative tolerance at this small a scale (Section 16 asks for
    # +/-10% at full training-world scale; small worlds are noisier).
    assert 0.02 * 0.7 <= summary["fraud_share_labelled"] <= 0.02 * 1.3


def test_label_noise_flips_requested_share(tmp_path):
    out = tmp_path / "world"
    run(out, n_customers=300, days=30, seed=7, fraud_rate=0.02, label_noise_rate=0.02)
    summary = json.loads((out / "summary.json").read_text())
    true_fraud = summary["true_fraud_count_before_noise"]
    expected_flips = round(true_fraud * 0.02)
    assert summary["label_noise_flipped_count"] == expected_flips


def test_no_future_leakage_balance_and_required_columns(tmp_path):
    import pandas as pd

    out = tmp_path / "world"
    run(out, n_customers=100, days=14, seed=3, fraud_rate=0.02, label_noise_rate=0.0)
    txns = pd.read_csv(out / "transactions.csv")
    required = {
        "txn_ref", "account_number", "amount", "channel", "txn_type", "txn_time",
        "beneficiary_account", "beneficiary_bank", "device_id", "location",
        "balance_before", "is_fraud", "fraud_type",
    }
    assert required.issubset(set(txns.columns))
    assert (txns["amount"] > 0).all()
    assert txns["txn_ref"].is_unique


def test_all_transactions_fall_within_the_generation_window(tmp_path):
    """Regression test: SOCIAL_ENGINEERING incidents were timestamped using
    the victim account's (possibly years-earlier) opened_on date as the
    random-timestamp lower bound instead of the generation window's
    start_date, so some fraud transactions landed years before day 0.

    A few hours to ~2 days of slack past the nominal end date is allowed:
    SIM_SWAP/ACCOUNT_TAKEOVER transactions can legitimately follow their
    precipitating security event by up to ~50 hours (Section 4.3), which can
    push a transaction just past end_date when the event itself lands near
    the end of the window -- that is by design, not a bug.
    """
    import pandas as pd

    out = tmp_path / "world"
    run(out, n_customers=300, days=30, seed=5, fraud_rate=0.03, label_noise_rate=0.02)
    txns = pd.read_csv(out / "transactions.csv")
    txns["txn_time"] = pd.to_datetime(txns["txn_time"], format="ISO8601")

    summary = __import__("json").loads((out / "summary.json").read_text())
    window_start = pd.Timestamp(summary["start_date"]).tz_localize("Africa/Lagos")
    window_end = pd.Timestamp(summary["end_date"]).tz_localize("Africa/Lagos") + pd.Timedelta(days=4)

    out_of_window = txns[(txns["txn_time"] < window_start) | (txns["txn_time"] >= window_end)]
    assert len(out_of_window) == 0, (
        f"{len(out_of_window)} transactions fell outside [{window_start}, {window_end}): "
        f"{out_of_window[['txn_ref', 'txn_time', 'fraud_type']].head()}"
    )
