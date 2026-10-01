"""Turn a raw synthetic world (customers/accounts/transactions/security_events
CSVs) into a feature table for training (Section 6.1 step 1).

Usage:
    python -m pipeline.build_features --in data/synthetic/train --out data/processed/train_features.parquet
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from fraud_core.features import compute_features_batch


def build(in_dir: Path, out_path: Path) -> None:
    transactions = pd.read_csv(in_dir / "transactions.csv")
    accounts = pd.read_csv(in_dir / "accounts.csv")
    security_events = pd.read_csv(in_dir / "security_events.csv")

    accounts["opened_on"] = pd.to_datetime(accounts["opened_on"]).dt.date

    global_median_amount = float(transactions["amount"].median())

    features = compute_features_batch(transactions, security_events, accounts, global_median_amount)

    merged = transactions[["txn_ref", "account_number", "is_fraud", "fraud_type", "amount", "channel", "txn_time"]].merge(
        features, on="txn_ref", how="left"
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_parquet(out_path, index=False)

    meta_path = out_path.parent / "feature_meta.json"
    meta = {}
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
    meta[out_path.stem] = {
        "global_median_amount": global_median_amount,
        "n_rows": len(merged),
        "n_fraud": int(merged["is_fraud"].sum()),
        "source_dir": str(in_dir),
    }
    # Also keep a top-level key for convenience when there is a single world.
    meta["global_median_amount"] = global_median_amount
    meta_path.write_text(json.dumps(meta, indent=2))

    print(f"Wrote {len(merged)} feature rows to {out_path} (global_median_amount={global_median_amount:.2f})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a feature table from a raw synthetic world")
    parser.add_argument("--in", dest="in_dir", required=True, type=Path)
    parser.add_argument("--out", dest="out_path", required=True, type=Path)
    args = parser.parse_args()
    build(args.in_dir, args.out_path)


if __name__ == "__main__":
    main()
