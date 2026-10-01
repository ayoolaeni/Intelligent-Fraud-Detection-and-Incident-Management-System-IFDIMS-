"""Mandatory feature parity test (Section 15.2): generate a small synthetic
world, load it into the test database, then for randomly chosen transactions
compare compute_features_batch's output with the online path
(feature_service reading from the DB). All values must match to 1e-6.
"""
from __future__ import annotations

import math
import random

import pandas as pd
import pytest

from fraud_core.constants import FEATURE_NAMES
from fraud_core.features import compute_features_batch
from generator.generate_synthetic import run as generate_synthetic_world


def _load_world_into_db(db_session, world_dir):
    from app.models.customer import Account, Customer
    from app.models.misc import SecurityEvent
    from app.models.transaction import Txn

    customers_df = pd.read_csv(world_dir / "customers.csv")
    accounts_df = pd.read_csv(world_dir / "accounts.csv")
    transactions_df = pd.read_csv(world_dir / "transactions.csv")
    security_events_df = pd.read_csv(world_dir / "security_events.csv")

    customer_id_map = {}
    for _, row in customers_df.iterrows():
        customer = Customer(
            bvn_hash="h" * 64, full_name=row["full_name"], phone_hash="p" * 64,
            phone_last4=str(row["phone"])[-4:], date_joined=pd.to_datetime(row["date_joined"]).date(),
            risk_profile="low",
        )
        db_session.add(customer)
        db_session.flush()
        customer_id_map[row["customer_id"]] = customer.customer_id

    account_id_map = {}
    for _, row in accounts_df.iterrows():
        account = Account(
            customer_id=customer_id_map[row["customer_id"]], account_number=str(row["account_number"]),
            account_type=row["account_type"], opened_on=pd.to_datetime(row["opened_on"]).date(), status="ACTIVE",
        )
        db_session.add(account)
        db_session.flush()
        account_id_map[str(row["account_number"])] = account.account_id

    for _, row in transactions_df.iterrows():
        txn = Txn(
            txn_ref=row["txn_ref"], account_id=account_id_map[str(row["account_number"])], amount=row["amount"],
            channel=row["channel"], txn_type=row["txn_type"], txn_time=pd.to_datetime(row["txn_time"]),
            beneficiary_account=(None if pd.isna(row["beneficiary_account"]) else str(row["beneficiary_account"])),
            beneficiary_bank=(None if pd.isna(row["beneficiary_bank"]) else str(row["beneficiary_bank"])),
            device_id=(None if pd.isna(row["device_id"]) else str(row["device_id"])),
            location=row["location"], balance_before=row["balance_before"], status="HISTORICAL",
        )
        db_session.add(txn)

    for _, row in security_events_df.iterrows():
        db_session.add(SecurityEvent(
            account_id=account_id_map[str(row["account_number"])], event_type=row["event_type"],
            event_time=pd.to_datetime(row["event_time"]),
        ))

    db_session.commit()
    return account_id_map


@pytest.mark.slow
def test_online_matches_batch_features(db_session, tmp_path):
    from app.models.customer import Account
    from app.services.feature_service import compute_features_for_txn

    world_dir = tmp_path / "parity_world"
    generate_synthetic_world(world_dir, n_customers=200, days=14, seed=99, fraud_rate=0.02, label_noise_rate=0.0)

    account_id_map = _load_world_into_db(db_session, world_dir)

    transactions_df = pd.read_csv(world_dir / "transactions.csv")
    accounts_df = pd.read_csv(world_dir / "accounts.csv")
    security_events_df = pd.read_csv(world_dir / "security_events.csv")
    accounts_df["opened_on"] = pd.to_datetime(accounts_df["opened_on"]).dt.date

    global_median = float(transactions_df["amount"].median())
    batch_features = compute_features_batch(transactions_df, security_events_df, accounts_df, global_median)
    batch_by_ref = batch_features.set_index("txn_ref")

    rng = random.Random(7)
    sample_refs = rng.sample(list(transactions_df["txn_ref"]), k=300)

    mismatches = []
    for txn_ref in sample_refs:
        row = transactions_df[transactions_df["txn_ref"] == txn_ref].iloc[0]
        account = db_session.query(Account).filter(Account.account_number == str(row["account_number"])).one()

        txn_dict = {
            "amount": float(row["amount"]),
            "channel": row["channel"],
            "txn_type": row["txn_type"],
            "txn_time": pd.to_datetime(row["txn_time"]),
            "beneficiary_account": None if pd.isna(row["beneficiary_account"]) else str(row["beneficiary_account"]),
            "device_id": None if pd.isna(row["device_id"]) else str(row["device_id"]),
            "location": row["location"],
            "balance_before": float(row["balance_before"]),
        }
        online_feats = compute_features_for_txn(db_session, account, txn_dict, global_median)
        batch_row = batch_by_ref.loc[txn_ref]

        for name in FEATURE_NAMES:
            online_val = float(online_feats[name])
            batch_val = float(batch_row[name])
            if not math.isclose(online_val, batch_val, abs_tol=1e-6, rel_tol=1e-6):
                mismatches.append((txn_ref, name, online_val, batch_val))

    assert not mismatches, f"{len(mismatches)} feature mismatches, e.g. {mismatches[:5]}"
