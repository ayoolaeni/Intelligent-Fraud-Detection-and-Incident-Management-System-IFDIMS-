"""Turn locust's raw --csv output into reports/loadtest_summary.md
(Section 15.4). Run after locust: python -m loadtest.summarize
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

TARGET_AVG_MS = 500.0


def run(stats_csv: Path, out_md: Path) -> None:
    df = pd.read_csv(stats_csv)
    row = df[df["Name"] == "/api/v1/transactions/score"]
    if row.empty:
        row = df[df["Type"] == "Aggregated"] if "Type" in df.columns else df.tail(1)
    row = row.iloc[0]

    avg_ms = float(row["Average Response Time"])
    median_ms = float(row["Median Response Time"])
    p95_ms = float(row.get("95%", row.get("95%ile (ms)", float("nan"))))
    throughput = float(row["Requests/s"])
    failures = int(row.get("Failure Count", 0))
    total = int(row.get("Request Count", 0))

    meets_target = avg_ms < TARGET_AVG_MS

    lines = [
        "# Load test summary",
        "",
        f"- Total requests: {total}",
        f"- Failures: {failures}",
        f"- Throughput: {throughput:.2f} req/s",
        f"- Average latency: {avg_ms:.1f} ms",
        f"- Median latency: {median_ms:.1f} ms",
        f"- 95th percentile latency: {p95_ms:.1f} ms",
        "",
        f"**Target: average latency < {TARGET_AVG_MS:.0f} ms -> {'PASS' if meets_target else 'FAIL'}**",
    ]
    out_md.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stats-csv", type=Path, default=Path("reports/loadtest_stats.csv"))
    parser.add_argument("--out", type=Path, default=Path("reports/loadtest_summary.md"))
    args = parser.parse_args()
    run(args.stats_csv, args.out)


if __name__ == "__main__":
    main()
