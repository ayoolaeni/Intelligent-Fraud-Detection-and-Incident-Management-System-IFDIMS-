"""Replay the demo world's transactions from day 46 onward against the live
scoring API, in time order, sending security events just before their time
(Section 17.2).

Usage:
    python -m simulator.stream --world data/synthetic/demo --api-url http://localhost:8000 \\
        --api-key sim-key-change-me --rate 5 --limit 2000
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests


def _row_to_txn_payload(row) -> dict:
    return {
        "txn_ref": row["txn_ref"],
        "account_number": str(row["account_number"]),
        "amount": str(row["amount"]),
        "channel": row["channel"],
        "txn_type": row["txn_type"],
        "txn_time": row["txn_time"].isoformat(),
        "beneficiary_account": None if pd.isna(row["beneficiary_account"]) else str(row["beneficiary_account"]),
        "beneficiary_bank": None if pd.isna(row["beneficiary_bank"]) else str(row["beneficiary_bank"]),
        "device_id": None if pd.isna(row["device_id"]) else str(row["device_id"]),
        "location": row["location"],
        "balance_before": str(row["balance_before"]),
    }


def build_timeline(world_dir: Path, limit: int | None):
    anchor = json.loads((world_dir / "anchor.json").read_text())
    offset_seconds = anchor["offset_seconds"]
    day45_boundary = datetime.fromisoformat(anchor["day45_boundary"])
    offset = pd.Timedelta(seconds=offset_seconds)

    transactions_df = pd.read_csv(world_dir / "transactions.csv")
    transactions_df["txn_time"] = pd.to_datetime(transactions_df["txn_time"], format="ISO8601")
    future_txns = transactions_df[transactions_df["txn_time"] >= day45_boundary].copy()
    future_txns["txn_time"] = future_txns["txn_time"] + offset
    future_txns = future_txns.sort_values("txn_time")
    if limit:
        future_txns = future_txns.head(limit)

    security_events_df = pd.read_csv(world_dir / "security_events.csv")
    future_events = security_events_df.iloc[0:0]
    if len(security_events_df):
        security_events_df["event_time"] = pd.to_datetime(security_events_df["event_time"], format="ISO8601")
        future_events = security_events_df[security_events_df["event_time"] >= day45_boundary].copy()
        future_events["event_time"] = future_events["event_time"] + offset

    items = [{"time": r["txn_time"], "kind": "txn", "row": r} for _, r in future_txns.iterrows()]
    items += [{"time": r["event_time"], "kind": "event", "row": r} for _, r in future_events.iterrows()]
    items.sort(key=lambda x: x["time"])
    return items


def run(world_dir: Path, api_url: str, api_key: str, rate: float, speedup: float | None, limit: int | None,
        reports_dir: Path) -> None:
    timeline = build_timeline(world_dir, limit)
    if not timeline:
        print("Nothing to stream (check anchor.json / --limit).")
        return

    headers = {"X-API-Key": api_key}
    sent = approved = held = errors = 0
    band_counts = {"low": 0, "medium": 0, "high": 0}
    latencies: list[float] = []
    results: list[dict] = []

    sim_start_wall = time.time()
    sim_start_time = timeline[0]["time"]

    for item in timeline:
        if speedup:
            elapsed_sim = (item["time"] - sim_start_time).total_seconds() / speedup
            elapsed_wall = time.time() - sim_start_wall
            if elapsed_sim > elapsed_wall:
                time.sleep(elapsed_sim - elapsed_wall)
        elif rate:
            time.sleep(1.0 / rate)

        row = item["row"]
        if item["kind"] == "event":
            payload = {
                "account_number": str(row["account_number"]),
                "event_type": row["event_type"],
                "event_time": row["event_time"].isoformat(),
            }
            try:
                requests.post(f"{api_url}/api/v1/security-events", json=payload, headers=headers, timeout=10)
            except requests.RequestException as exc:
                print(f"[event error] {exc}")
            continue

        payload = _row_to_txn_payload(row)
        start = time.perf_counter()
        try:
            resp = requests.post(f"{api_url}/api/v1/transactions/score", json=payload, headers=headers, timeout=10)
            latency_ms = (time.perf_counter() - start) * 1000
            sent += 1
            if resp.status_code == 200:
                body = resp.json()
                band_counts[body["risk_band"]] += 1
                if body["decision"] == "HOLD":
                    held += 1
                else:
                    approved += 1
                latencies.append(latency_ms)
                results.append({
                    "txn_ref": row["txn_ref"],
                    "is_fraud_true": int(row["is_fraud"]),
                    "fraud_type_true": row.get("fraud_type"),
                    "fraud_score": body["fraud_score"],
                    "risk_band": body["risk_band"],
                    "decision": body["decision"],
                    "latency_ms": latency_ms,
                })
            else:
                errors += 1
                print(f"[score error {resp.status_code}] {resp.text[:200]}")
        except requests.RequestException as exc:
            errors += 1
            print(f"[score error] {exc}")

        if sent % 50 == 0 and sent > 0:
            avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
            print(f"sent={sent} approved={approved} held={held} bands={band_counts} errors={errors} avg_latency={avg_latency:.1f}ms")

    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    print(f"\nDone. sent={sent} approved={approved} held={held} bands={band_counts} errors={errors} avg_latency={avg_latency:.1f}ms")

    df = pd.DataFrame(results)
    reports_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(reports_dir / "demo_stream_results.csv", index=False)

    if len(df):
        df["predicted_fraud"] = df["risk_band"].isin(["medium", "high"]).astype(int)
        tp = int(((df.is_fraud_true == 1) & (df.predicted_fraud == 1)).sum())
        fp = int(((df.is_fraud_true == 0) & (df.predicted_fraud == 1)).sum())
        fn = int(((df.is_fraud_true == 1) & (df.predicted_fraud == 0)).sum())
        tn = int(((df.is_fraud_true == 0) & (df.predicted_fraud == 0)).sum())
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        print(f"\nConfusion matrix (flagged = medium or high band) vs hidden is_fraud label:")
        print(f"  TP={tp} FP={fp} FN={fn} TN={tn}  precision={precision:.3f} recall={recall:.3f}")

    print(f"\nWrote {reports_dir / 'demo_stream_results.csv'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Stream the demo world's transactions to the live scoring API")
    parser.add_argument("--world", required=True, type=Path)
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--rate", type=float, default=5.0, help="Transactions per second (ignored if --speedup is set)")
    parser.add_argument("--speedup", type=float, default=None, help="Replay X times faster than real elapsed time")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--reports-dir", type=Path, default=Path("reports"))
    args = parser.parse_args()
    run(args.world, args.api_url, args.api_key, args.rate, args.speedup, args.limit, args.reports_dir)


if __name__ == "__main__":
    main()
