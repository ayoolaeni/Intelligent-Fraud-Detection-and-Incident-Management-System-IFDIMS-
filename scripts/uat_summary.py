"""Summarise UAT questionnaire responses: mean and standard deviation per
statement and per group (Section 15.5).

Expects a CSV with one row per respondent and columns Q1..Q12 matching
docs/UAT_QUESTIONNAIRE.md (Likert 1-5).

Usage:
    python scripts/uat_summary.py --responses reports/uat_responses.csv --out reports/uat_summary.csv
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

GROUPS = {
    "usefulness": ["Q1", "Q2", "Q3"],
    "ease_of_use": ["Q4", "Q5", "Q6"],
    "clarity_of_explanations": ["Q7", "Q8", "Q9"],
    "case_handling": ["Q10", "Q11", "Q12"],
}


def run(responses_csv: Path, out_csv: Path) -> None:
    if not responses_csv.exists():
        print(f"[skip] {responses_csv} not found; nothing to summarise yet.")
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(columns=["item", "mean", "std", "n"]).to_csv(out_csv, index=False)
        return

    df = pd.read_csv(responses_csv)
    rows = []
    for question, group in [(q, g) for g, qs in GROUPS.items() for q in qs]:
        if question not in df.columns:
            continue
        series = df[question].dropna()
        rows.append({"item": question, "group": group, "mean": series.mean(), "std": series.std(), "n": len(series)})

    for group, questions in GROUPS.items():
        cols = [q for q in questions if q in df.columns]
        if not cols:
            continue
        stacked = df[cols].values.flatten()
        stacked = stacked[~pd.isna(stacked)]
        rows.append({"item": f"GROUP:{group}", "group": group, "mean": stacked.mean(), "std": stacked.std(), "n": len(stacked)})

    out_df = pd.DataFrame(rows)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_csv, index=False)
    print(out_df.to_string(index=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--responses", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.responses, args.out)


if __name__ == "__main__":
    main()
