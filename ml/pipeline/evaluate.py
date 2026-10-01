"""Produce the Chapter Four evaluation outputs (Section 6.2).

Usage:
    python -m pipeline.evaluate --model-dir models/<version>
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
from sklearn.metrics import ConfusionMatrixDisplay, RocCurveDisplay, PrecisionRecallDisplay

from fraud_core.constants import FEATURE_LABELS, FEATURE_NAMES
from pipeline.common import compute_metrics, to_feature_matrix

REPORTS_DIR_DEFAULT = Path("reports")


def _score_isolation_forest(iso_bundle: dict, X: pd.DataFrame) -> np.ndarray:
    model = iso_bundle["model"]
    scaler = iso_bundle["scaler"]
    raw = -model.score_samples(X)
    return scaler.transform(raw.reshape(-1, 1)).ravel()


def run(model_dir: Path, reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)

    metadata = json.loads((model_dir / "metadata.json").read_text())
    family_models = joblib.load(model_dir / "family_models.joblib")
    test_df = pd.read_parquet(model_dir / "test_predictions.parquet")
    X_test = to_feature_matrix(test_df)
    y_test = test_df["is_fraud"].astype(int)

    all_scores: dict[str, np.ndarray] = {}
    rows = []
    for algorithm, pipeline in family_models["supervised"].items():
        scores = pipeline.predict_proba(X_test)[:, 1]
        all_scores[algorithm] = scores
        m = compute_metrics(y_test, scores)
        rows.append({
            "model": algorithm,
            "precision": m["precision"], "recall": m["recall"], "f1": m["f1"],
            "false_positive_rate": m["false_positive_rate"],
            "roc_auc": m["roc_auc"], "pr_auc": m["pr_auc"],
            "latency_ms": metadata["latency_ms_per_prediction"] if algorithm == metadata["algorithm"] else None,
            "eligible_for_deployment": True,
        })

    iso_scores = _score_isolation_forest(family_models["isolation_forest"], X_test)
    all_scores["isolation_forest"] = iso_scores
    m = compute_metrics(y_test, iso_scores)
    rows.append({
        "model": "isolation_forest",
        "precision": m["precision"], "recall": m["recall"], "f1": m["f1"],
        "false_positive_rate": m["false_positive_rate"],
        "roc_auc": m["roc_auc"], "pr_auc": m["pr_auc"],
        "latency_ms": None,
        "eligible_for_deployment": False,
    })

    comparison_df = pd.DataFrame(rows)
    comparison_df.to_csv(reports_dir / "model_comparison.csv", index=False)
    with open(reports_dir / "model_comparison.md", "w") as f:
        f.write(comparison_df.to_markdown(index=False))
    print(comparison_df.to_string(index=False))

    # Confusion matrices
    for algorithm, scores in all_scores.items():
        y_pred = (scores >= 0.5).astype(int)
        fig, ax = plt.subplots(figsize=(4, 4))
        ConfusionMatrixDisplay.from_predictions(y_test, y_pred, ax=ax, colorbar=False)
        ax.set_title(f"Confusion matrix: {algorithm}")
        fig.tight_layout()
        fig.savefig(reports_dir / f"confusion_{algorithm}.png", dpi=150)
        plt.close(fig)

    # ROC and PR curves, all models on one chart each
    fig, ax = plt.subplots(figsize=(6, 6))
    for algorithm, scores in all_scores.items():
        RocCurveDisplay.from_predictions(y_test, scores, name=algorithm, ax=ax)
    ax.set_title("ROC curves")
    fig.tight_layout()
    fig.savefig(reports_dir / "roc_curves.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6, 6))
    for algorithm, scores in all_scores.items():
        PrecisionRecallDisplay.from_predictions(y_test, scores, name=algorithm, ax=ax)
    ax.set_title("Precision-Recall curves")
    fig.tight_layout()
    fig.savefig(reports_dir / "pr_curves.png", dpi=150)
    plt.close(fig)

    # SHAP summary + examples for the selected model
    selected_algorithm = metadata["algorithm"]
    selected_pipeline = family_models["supervised"][selected_algorithm]
    sample = X_test.sample(n=min(1000, len(X_test)), random_state=42)
    clf = selected_pipeline.named_steps["clf"]
    if selected_algorithm == "logistic_regression":
        scaler = selected_pipeline.named_steps["scaler"]
        sample_scaled = pd.DataFrame(scaler.transform(sample), columns=sample.columns, index=sample.index)
        explainer = shap.LinearExplainer(clf, sample_scaled)
        shap_values = explainer.shap_values(sample_scaled)
    else:
        explainer = shap.TreeExplainer(clf)
        shap_values = explainer.shap_values(sample, check_additivity=False)
        if isinstance(shap_values, list):
            shap_values = shap_values[1]
        if hasattr(shap_values, "ndim") and shap_values.ndim == 3:
            shap_values = shap_values[:, :, 1]

    display_names = [FEATURE_LABELS.get(f, f) for f in FEATURE_NAMES]
    fig = plt.figure(figsize=(8, 8))
    shap.summary_plot(shap_values, sample, feature_names=display_names, show=False)
    fig.tight_layout()
    fig.savefig(reports_dir / "shap_summary.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    fraud_rows = test_df[test_df["is_fraud"] == 1]
    example_idx = fraud_rows.sample(n=min(3, len(fraud_rows)), random_state=42).index if len(fraud_rows) else []
    for n, idx in enumerate(example_idx, start=1):
        row = X_test.loc[[idx]]
        if selected_algorithm == "logistic_regression":
            row_scaled = pd.DataFrame(scaler.transform(row), columns=row.columns)
            row_shap = explainer.shap_values(row_scaled)[0]
        else:
            rs = explainer.shap_values(row, check_additivity=False)
            if isinstance(rs, list):
                rs = rs[1]
            if hasattr(rs, "ndim") and rs.ndim == 3:
                rs = rs[:, :, 1]
            row_shap = rs[0]
        order = np.argsort(-np.abs(row_shap))[:10]
        fig, ax = plt.subplots(figsize=(7, 5))
        ax.barh(
            [display_names[i] for i in order][::-1],
            [row_shap[i] for i in order][::-1],
            color=["#d62728" if row_shap[i] > 0 else "#1f77b4" for i in order][::-1],
        )
        ax.set_title(f"Top factors for fraud example {n} (txn_ref={test_df.loc[idx, 'txn_ref']})")
        fig.tight_layout()
        fig.savefig(reports_dir / f"shap_example_{n}.png", dpi=150)
        plt.close(fig)

    # Threshold analysis: precision, recall, alerts per 1,000 for thresholds 0.10..0.90
    selected_scores = all_scores[selected_algorithm]
    threshold_rows = []
    for t in np.arange(0.10, 0.901, 0.05):
        t = round(float(t), 2)
        y_pred = (selected_scores >= t).astype(int)
        from sklearn.metrics import precision_score, recall_score
        threshold_rows.append({
            "threshold": t,
            "precision": precision_score(y_test, y_pred, zero_division=0),
            "recall": recall_score(y_test, y_pred, zero_division=0),
            "alerts_per_1000": (y_pred.sum() / len(y_pred)) * 1000,
        })
    pd.DataFrame(threshold_rows).to_csv(reports_dir / "threshold_analysis.csv", index=False)

    # Recall per fraud_type on the test set (selected model, threshold 0.5)
    y_pred_selected = (selected_scores >= 0.5).astype(int)
    test_df_eval = test_df.assign(y_pred=y_pred_selected)
    fraud_type_rows = []
    for fraud_type, group in test_df_eval[test_df_eval["is_fraud"] == 1].groupby("fraud_type"):
        recall = group["y_pred"].mean()
        fraud_type_rows.append({"fraud_type": fraud_type, "n": len(group), "recall": recall})
    pd.DataFrame(fraud_type_rows).to_csv(reports_dir / "fraud_type_recall.csv", index=False)

    print(f"\nAll Chapter Four evaluation outputs written to {reports_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate all trained model families and write Chapter Four outputs")
    parser.add_argument("--model-dir", required=True, type=Path)
    parser.add_argument("--reports-dir", default=REPORTS_DIR_DEFAULT, type=Path)
    args = parser.parse_args()
    run(args.model_dir, args.reports_dir)


if __name__ == "__main__":
    main()
