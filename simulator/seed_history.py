"""Load the demo world's customers, accounts, security events and first 45
days of transactions into the database as HISTORICAL (not scored) records
(Section 17.1).

Usage:
    python -m simulator.seed_history --world data/synthetic/demo --anchor-now
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import uuid
from datetime import timedelta
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text


def _hash(salt: str, value: str) -> str:
    return hashlib.sha256((salt + str(value)).encode("utf-8")).hexdigest()


def run(world_dir: Path, database_url: str, bvn_salt: str, phone_salt: str, anchor_now: bool) -> None:
    customers_df = pd.read_csv(world_dir / "customers.csv")
    accounts_df = pd.read_csv(world_dir / "accounts.csv")
    transactions_df = pd.read_csv(world_dir / "transactions.csv")
    security_events_df = pd.read_csv(world_dir / "security_events.csv")

    transactions_df["txn_time"] = pd.to_datetime(transactions_df["txn_time"], format="ISO8601")
    if len(security_events_df):
        security_events_df["event_time"] = pd.to_datetime(security_events_df["event_time"], format="ISO8601")

    start = transactions_df["txn_time"].min().normalize()
    day45_boundary = start + timedelta(days=45)

    offset = timedelta(0)
    if anchor_now:
        import datetime as dt

        now = dt.datetime.now(tz=day45_boundary.tzinfo)
        offset = now - day45_boundary

    history_txns = transactions_df[transactions_df["txn_time"] < day45_boundary].copy()
    history_txns["txn_time"] = history_txns["txn_time"] + offset
    history_events = security_events_df[security_events_df["event_time"] < day45_boundary].copy() if len(security_events_df) else security_events_df
    if len(history_events):
        history_events["event_time"] = history_events["event_time"] + offset

    accounts_df["opened_on"] = pd.to_datetime(accounts_df["opened_on"]) + offset
    accounts_df["opened_on"] = accounts_df["opened_on"].dt.date
    customers_df["date_joined"] = pd.to_datetime(customers_df["date_joined"]) + offset
    customers_df["date_joined"] = customers_df["date_joined"].dt.date

    engine = create_engine(database_url)
    with engine.begin() as conn:
        customer_id_map: dict[str, str] = {}
        customer_rows = []
        for _, row in customers_df.iterrows():
            cid = str(uuid.uuid4())
            customer_id_map[row["customer_id"]] = cid
            customer_rows.append({
                "customer_id": cid,
                "bvn_hash": _hash(bvn_salt, row["bvn"]),
                "full_name": row["full_name"],
                "phone_hash": _hash(phone_salt, row["phone"]),
                "phone_last4": str(row["phone"])[-4:],
                "date_joined": row["date_joined"],
                "risk_profile": "low",
            })
        conn.execute(text(
            "INSERT INTO customer (customer_id, bvn_hash, full_name, phone_hash, phone_last4, date_joined, risk_profile) "
            "VALUES (:customer_id, :bvn_hash, :full_name, :phone_hash, :phone_last4, :date_joined, :risk_profile)"
        ), customer_rows)
        print(f"Inserted {len(customer_rows)} customers")

        account_id_map: dict[str, str] = {}
        account_rows = []
        for _, row in accounts_df.iterrows():
            aid = str(uuid.uuid4())
            account_id_map[str(row["account_number"])] = aid
            account_rows.append({
                "account_id": aid,
                "customer_id": customer_id_map[row["customer_id"]],
                "account_number": str(row["account_number"]),
                "account_type": row["account_type"],
                "opened_on": row["opened_on"],
                "status": "ACTIVE",
            })
        conn.execute(text(
            "INSERT INTO account (account_id, customer_id, account_number, account_type, opened_on, status) "
            "VALUES (:account_id, :customer_id, :account_number, :account_type, :opened_on, :status)"
        ), account_rows)
        print(f"Inserted {len(account_rows)} accounts")

        txn_rows = []
        for _, row in history_txns.iterrows():
            txn_rows.append({
                "txn_id": str(uuid.uuid4()),
                "txn_ref": row["txn_ref"],
                "account_id": account_id_map[str(row["account_number"])],
                "amount": float(row["amount"]),
                "channel": row["channel"],
                "txn_type": row["txn_type"],
                "txn_time": row["txn_time"].to_pydatetime(),
                "beneficiary_account": None if pd.isna(row["beneficiary_account"]) else str(row["beneficiary_account"]),
                "beneficiary_bank": None if pd.isna(row["beneficiary_bank"]) else str(row["beneficiary_bank"]),
                "device_id": None if pd.isna(row["device_id"]) else str(row["device_id"]),
                "location": row["location"],
                "balance_before": float(row["balance_before"]),
                "status": "HISTORICAL",
            })
        if txn_rows:
            conn.execute(text(
                "INSERT INTO txn (txn_id, txn_ref, account_id, amount, channel, txn_type, txn_time, "
                "beneficiary_account, beneficiary_bank, device_id, location, balance_before, status) "
                "VALUES (:txn_id, :txn_ref, :account_id, :amount, :channel, :txn_type, :txn_time, "
                ":beneficiary_account, :beneficiary_bank, :device_id, :location, :balance_before, :status)"
            ), txn_rows)
        print(f"Inserted {len(txn_rows)} historical transactions")

        event_rows = []
        if len(history_events):
            for _, row in history_events.iterrows():
                event_rows.append({
                    "event_id": str(uuid.uuid4()),
                    "account_id": account_id_map[str(row["account_number"])],
                    "event_type": row["event_type"],
                    "event_time": row["event_time"].to_pydatetime(),
                })
            conn.execute(text(
                "INSERT INTO security_event (event_id, account_id, event_type, event_time) "
                "VALUES (:event_id, :account_id, :event_type, :event_time)"
            ), event_rows)
        print(f"Inserted {len(event_rows)} historical security events")

    anchor_path = world_dir / "anchor.json"
    anchor_path.write_text(json.dumps({
        "offset_seconds": offset.total_seconds(),
        "day45_boundary": day45_boundary.isoformat(),
    }, indent=2))
    print(f"Wrote {anchor_path} (offset={offset})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the database with the demo world's first 45 days of history")
    parser.add_argument("--world", required=True, type=Path)
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--bvn-salt", default=os.environ.get("BVN_SALT", "change-me"))
    parser.add_argument("--phone-salt", default=os.environ.get("PHONE_SALT", "change-me"))
    parser.add_argument("--anchor-now", action="store_true")
    args = parser.parse_args()
    if not args.database_url:
        raise SystemExit("DATABASE_URL must be set (env var or --database-url)")
    run(args.world, args.database_url, args.bvn_salt, args.phone_salt, args.anchor_now)


if __name__ == "__main__":
    main()
