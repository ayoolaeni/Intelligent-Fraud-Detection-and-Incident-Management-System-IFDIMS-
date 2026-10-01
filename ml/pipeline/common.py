"""Shared helpers for the training/evaluation pipeline (Section 6)."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)

from fraud_core.constants import FEATURE_NAMES

REPORTING_THRESHOLD = 0.5  # see docs/DECISIONS.md D15
DEFAULT_MEDIUM_THRESHOLD = 0.40
DEFAULT_HIGH_THRESHOLD = 0.70
RANDOM_STATE = 42


def stratified_split(df: pd.DataFrame, label_col: str = "is_fraud"):
    """70/15/15 stratified split on ``label_col``, random_state=42 (Section 6.1 step 2)."""
    from sklearn.model_selection import train_test_split

    train_df, temp_df = train_test_split(
        df, test_size=0.30, stratify=df[label_col], random_state=RANDOM_STATE
    )
    val_df, test_df = train_test_split(
        temp_df, test_size=0.50, stratify=temp_df[label_col], random_state=RANDOM_STATE
    )
    return train_df.reset_index(drop=True), val_df.reset_index(drop=True), test_df.reset_index(drop=True)


def compute_metrics(y_true, scores, threshold: float = REPORTING_THRESHOLD) -> dict:
    y_pred = (np.asarray(scores) >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    return {
        "threshold": threshold,
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "false_positive_rate": float(fpr),
        "roc_auc": float(roc_auc_score(y_true, scores)) if len(set(y_true)) > 1 else float("nan"),
        "pr_auc": float(average_precision_score(y_true, scores)),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
    }


def precision_recall_at(y_true, scores, threshold: float) -> dict:
    y_pred = (np.asarray(scores) >= threshold).astype(int)
    return {
        "threshold": threshold,
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
    }


def suggest_thresholds(y_val, scores) -> dict:
    """Section 6.1 step 8."""
    precisions, recalls, thresholds = precision_recall_curve(y_val, scores)
    # precision_recall_curve returns arrays of len(thresholds)+1; drop the last
    # precision/recall point (which has no corresponding threshold).
    precisions, recalls = precisions[:-1], recalls[:-1]

    high_mask = precisions >= 0.80
    if high_mask.any():
        idx = np.argmax(np.where(high_mask, recalls, -1))
        suggested_high = float(thresholds[idx])
    else:
        suggested_high = DEFAULT_HIGH_THRESHOLD

    medium_mask = recalls >= 0.95
    if medium_mask.any():
        idx = np.argmax(np.where(medium_mask, thresholds, -1))
        suggested_medium = float(thresholds[idx])
    else:
        suggested_medium = DEFAULT_MEDIUM_THRESHOLD

    return {
        "suggested_medium_threshold": suggested_medium,
        "suggested_high_threshold": suggested_high,
    }


def measure_latency_ms(predict_one_fn, X: pd.DataFrame, n: int = 1000, seed: int = RANDOM_STATE) -> float:
    """Average wall-clock time per single-row prediction (Section 6.1 step 6),
    including SHAP, in milliseconds. ``predict_one_fn`` takes a single-row
    DataFrame and returns (score, shap_values).
    """
    rng = np.random.default_rng(seed)
    n = min(n, len(X))
    idx = rng.choice(len(X), size=n, replace=False)
    start = time.perf_counter()
    for i in idx:
        row = X.iloc[[i]]
        predict_one_fn(row)
    elapsed = time.perf_counter() - start
    return (elapsed / n) * 1000.0


def to_feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in FEATURE_NAMES if c not in df.columns]
    if missing:
        raise ValueError(f"Feature table is missing columns: {missing}")
    return df[FEATURE_NAMES].astype(float)
