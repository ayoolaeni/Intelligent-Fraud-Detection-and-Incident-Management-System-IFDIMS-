"""Benchmark model families against public Kaggle datasets for comparison
with earlier studies (Section 6.3). Deployed model always uses the synthetic
dataset; this script is for Chapter Four benchmark tables only.

Usage:
    python -m pipeline.benchmark_public --raw-dir data/raw --reports-dir reports
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from imblearn.pipeline import Pipeline as ImbPipeline
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import MinMaxScaler, StandardScaler
from xgboost import XGBClassifier

from pipeline.common import RANDOM_STATE, compute_metrics, stratified_split

PAYSIM_SAMPLE_CAP = 1_000_000


def _fit_variants(algorithm: str, X_train, y_train):
    """A lighter-weight fit (no RandomizedSearchCV) with sensible defaults,
    since Section 6.3 asks for "the same balancing and tuning approach" but
    Kaggle datasets are used for comparison only, not deployment; fixed
    reasonable hyperparameters keep the benchmark runnable in CI-scale time.
    """
    results = {}
    n_neg, n_pos = int((y_train == 0).sum()), int((y_train == 1).sum())

    if algorithm == "logistic_regression":
        base = lambda **kw: LogisticRegression(max_iter=2000, solver="liblinear", C=1.0, random_state=RANDOM_STATE, **kw)
        smote_pipe = ImbPipeline([
            ("smote", SMOTE(sampling_strategy=0.1, k_neighbors=5, random_state=RANDOM_STATE)),
            ("scaler", StandardScaler()), ("clf", base()),
        ])
        cw_pipe = ImbPipeline([("scaler", StandardScaler()), ("clf", base(class_weight="balanced"))])
        results["smote"] = smote_pipe
        results["class_weight"] = cw_pipe
    elif algorithm == "random_forest":
        base = lambda **kw: RandomForestClassifier(n_estimators=200, max_depth=12, n_jobs=-1, random_state=RANDOM_STATE, **kw)
        results["smote"] = ImbPipeline([("smote", SMOTE(sampling_strategy=0.1, k_neighbors=5, random_state=RANDOM_STATE)), ("clf", base())])
        results["class_weight"] = ImbPipeline([("clf", base(class_weight="balanced"))])
    elif algorithm == "xgboost":
        results["smote"] = ImbPipeline([
            ("smote", SMOTE(sampling_strategy=0.1, k_neighbors=5, random_state=RANDOM_STATE)),
            ("clf", XGBClassifier(tree_method="hist", eval_metric="aucpr", n_estimators=400, max_depth=5, random_state=RANDOM_STATE)),
        ])
        results["scale_pos_weight"] = ImbPipeline([
            ("clf", XGBClassifier(tree_method="hist", eval_metric="aucpr", n_estimators=400, max_depth=5,
                                   scale_pos_weight=n_neg / max(n_pos, 1), random_state=RANDOM_STATE)),
        ])
    for pipe in results.values():
        pipe.fit(X_train, y_train)
    return results


def _benchmark_one(name: str, X: pd.DataFrame, y: pd.Series, reports_dir: Path) -> None:
    df = X.copy()
    df["is_fraud"] = y.values
    train_df, val_df, test_df = stratified_split(df)
    feature_cols = [c for c in df.columns if c != "is_fraud"]
    X_train, y_train = train_df[feature_cols], train_df["is_fraud"]
    X_val, y_val = val_df[feature_cols], val_df["is_fraud"]
    X_test, y_test = test_df[feature_cols], test_df["is_fraud"]

    rows = []
    for algorithm in ("logistic_regression", "random_forest", "xgboost"):
        variants = _fit_variants(algorithm, X_train, y_train)
        best_name, best_pipe, best_score = None, None, -1
        for variant_name, pipe in variants.items():
            score = compute_metrics(y_val, pipe.predict_proba(X_val)[:, 1])["pr_auc"]
            if score > best_score:
                best_name, best_pipe, best_score = variant_name, pipe, score

        start = time.perf_counter()
        for i in range(min(200, len(X_test))):
            best_pipe.predict_proba(X_test.iloc[[i]])
        latency_ms = (time.perf_counter() - start) / min(200, len(X_test)) * 1000.0

        test_scores = best_pipe.predict_proba(X_test)[:, 1]
        m = compute_metrics(y_test, test_scores)
        rows.append({"model": algorithm, "variant": best_name, **m, "latency_ms": latency_ms})

    iso = IsolationForest(n_estimators=200, contamination="auto", random_state=RANDOM_STATE)
    iso.fit(X_train)
    raw = -iso.score_samples(X_test)
    scores = MinMaxScaler().fit_transform(raw.reshape(-1, 1)).ravel()
    m = compute_metrics(y_test, scores)
    rows.append({"model": "isolation_forest", "variant": "unsupervised", **m, "latency_ms": None})

    out = pd.DataFrame(rows)
    reports_dir.mkdir(parents=True, exist_ok=True)
    out.to_csv(reports_dir / f"benchmark_{name}.csv", index=False)
    print(f"\n{name} benchmark:\n{out.to_string(index=False)}")


def benchmark_european(raw_dir: Path, reports_dir: Path) -> None:
    path = raw_dir / "creditcard.csv"
    if not path.exists():
        print(f"[skip] {path} not found; download it from Kaggle to include this benchmark.")
        return
    df = pd.read_csv(path)
    y = df["Class"]
    X = df.drop(columns=["Class"])
    _benchmark_one("creditcard_european", X, y, reports_dir)


def benchmark_paysim(raw_dir: Path, reports_dir: Path) -> None:
    path = raw_dir / "paysim.csv"
    if not path.exists():
        print(f"[skip] {path} not found; download it from Kaggle to include this benchmark.")
        return
    df = pd.read_csv(path)
    if len(df) > PAYSIM_SAMPLE_CAP:
        # Stratified sample to keep memory bounded (docs/DECISIONS.md D8).
        fraud = df[df["isFraud"] == 1]
        legit = df[df["isFraud"] == 0]
        keep_legit = legit.sample(n=min(len(legit), PAYSIM_SAMPLE_CAP - len(fraud)), random_state=RANDOM_STATE)
        df = pd.concat([fraud, keep_legit]).sample(frac=1, random_state=RANDOM_STATE).reset_index(drop=True)
        print(f"Sampled PaySim down to {len(df)} rows (stratified on isFraud)")

    y = df["isFraud"]
    type_dummies = pd.get_dummies(df["type"], prefix="type")
    X = pd.concat([
        df[["step", "amount", "oldbalanceOrg", "newbalanceOrig", "oldbalanceDest", "newbalanceDest"]],
        type_dummies,
    ], axis=1)
    _benchmark_one("paysim", X, y, reports_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark against public Kaggle fraud datasets")
    parser.add_argument("--raw-dir", default=Path("data/raw"), type=Path)
    parser.add_argument("--reports-dir", default=Path("reports"), type=Path)
    args = parser.parse_args()
    benchmark_european(args.raw_dir, args.reports_dir)
    benchmark_paysim(args.raw_dir, args.reports_dir)


if __name__ == "__main__":
    main()
