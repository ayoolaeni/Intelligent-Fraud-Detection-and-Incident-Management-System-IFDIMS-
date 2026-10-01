import numpy as np
import pandas as pd

from pipeline.common import compute_metrics, stratified_split, suggest_thresholds


def test_compute_metrics_perfect_separation():
    y = [0, 0, 0, 1, 1]
    scores = [0.1, 0.2, 0.3, 0.9, 0.95]
    m = compute_metrics(y, scores, threshold=0.5)
    assert m["precision"] == 1.0
    assert m["recall"] == 1.0
    assert m["false_positive_rate"] == 0.0


def test_suggest_thresholds_monotonic_scores():
    rng = np.random.default_rng(0)
    y = np.array([0] * 900 + [1] * 100)
    # scores correlated with label
    scores = np.where(y == 1, rng.uniform(0.5, 1.0, size=1000), rng.uniform(0.0, 0.6, size=1000))
    result = suggest_thresholds(y, scores)
    assert 0.0 <= result["suggested_medium_threshold"] <= 1.0
    assert 0.0 <= result["suggested_high_threshold"] <= 1.0


def test_stratified_split_preserves_fraud_ratio():
    df = pd.DataFrame({
        "is_fraud": [0] * 900 + [1] * 100,
        "x": range(1000),
    })
    train_df, val_df, test_df = stratified_split(df)
    assert len(train_df) + len(val_df) + len(test_df) == 1000
    for part in (train_df, val_df, test_df):
        ratio = part["is_fraud"].mean()
        assert abs(ratio - 0.10) < 0.03
