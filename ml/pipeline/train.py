"""Train, tune and select the fraud model (Section 6.1 steps 2-10).

Usage:
    python -m pipeline.train --features data/processed/train_features.parquet \\
        --meta data/processed/feature_meta.json --out-dir models \\
        [--extra-labels path/to/labels_export.csv]
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import shap
from imblearn.over_sampling import SMOTE
from imblearn.pipeline import Pipeline as ImbPipeline
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import RandomizedSearchCV, StratifiedKFold
from sklearn.preprocessing import MinMaxScaler, StandardScaler
from xgboost import XGBClassifier

from fraud_core.constants import FEATURE_NAMES
from pipeline.common import (
    RANDOM_STATE,
    compute_metrics,
    measure_latency_ms,
    precision_recall_at,
    stratified_split,
    suggest_thresholds,
    to_feature_matrix,
)

N_ITER = 20
N_SPLITS = 5

SEARCH_SPACES = {
    "logistic_regression": {"clf__C": [0.01, 0.1, 1, 10], "clf__penalty": ["l1", "l2"]},
    "random_forest": {
        "clf__n_estimators": [100, 200, 400],
        "clf__max_depth": [8, 12, 16, None],
        "clf__min_samples_leaf": [1, 2, 5],
    },
    "xgboost": {
        "clf__n_estimators": [200, 400, 600],
        "clf__max_depth": [3, 5, 7],
        "clf__learning_rate": [0.03, 0.1, 0.2],
        "clf__subsample": [0.7, 0.9, 1.0],
        "clf__colsample_bytree": [0.7, 0.9, 1.0],
    },
}
ISOLATION_FOREST_GRID = [
    {"n_estimators": n, "contamination": c}
    for n in (100, 300)
    for c in ("auto", 0.005, 0.01)
]


def _make_base_estimator(algorithm: str, *, class_weight_balanced: bool = False, scale_pos_weight: float | None = None):
    if algorithm == "logistic_regression":
        return LogisticRegression(
            max_iter=2000, solver="liblinear", random_state=RANDOM_STATE,
            class_weight="balanced" if class_weight_balanced else None,
        )
    if algorithm == "random_forest":
        return RandomForestClassifier(
            n_jobs=-1, random_state=RANDOM_STATE,
            class_weight="balanced" if class_weight_balanced else None,
        )
    if algorithm == "xgboost":
        kwargs = {}
        if scale_pos_weight is not None:
            kwargs["scale_pos_weight"] = scale_pos_weight
        return XGBClassifier(
            tree_method="hist", eval_metric="aucpr", random_state=RANDOM_STATE, **kwargs
        )
    raise ValueError(algorithm)


def _make_pipeline(algorithm: str, use_smote: bool, **estimator_kwargs) -> ImbPipeline:
    steps = []
    if use_smote:
        steps.append(("smote", SMOTE(sampling_strategy=0.1, k_neighbors=5, random_state=RANDOM_STATE)))
    if algorithm == "logistic_regression":
        steps.append(("scaler", StandardScaler()))
    steps.append(("clf", _make_base_estimator(algorithm, **estimator_kwargs)))
    return ImbPipeline(steps)


def _tune(algorithm: str, pipeline: ImbPipeline, X_train, y_train, cv):
    search = RandomizedSearchCV(
        pipeline,
        param_distributions=SEARCH_SPACES[algorithm],
        n_iter=N_ITER,
        scoring="average_precision",
        cv=cv,
        random_state=RANDOM_STATE,
        # Serial outer loop: RandomForestClassifier/XGBoost already parallelize
        # internally (n_jobs=-1 / default multi-threading), so an outer n_jobs=-1
        # here causes nested-parallelism oversubscription (N worker processes each
        # spawning their own full thread pool). On Windows this is compounded by
        # loky's per-dispatch process/memmap overhead, which was observed to turn
        # a sub-minute search into a 30+ minute hang with zero progress output.
        n_jobs=1,
        refit=True,
    )
    search.fit(X_train, y_train)
    return search.best_estimator_, search.best_params_, float(search.best_score_)


def train_supervised_family(algorithm: str, X_train, y_train, X_val, y_val, cv) -> dict:
    n_neg = int((y_train == 0).sum())
    n_pos = int((y_train == 1).sum())

    variants = {}
    variants["smote"] = _make_pipeline(algorithm, use_smote=True)
    if algorithm == "xgboost":
        variants["scale_pos_weight"] = _make_pipeline(
            algorithm, use_smote=False, scale_pos_weight=(n_neg / max(n_pos, 1))
        )
    else:
        variants["class_weight"] = _make_pipeline(algorithm, use_smote=False, class_weight_balanced=True)

    results = {}
    for variant_name, pipeline in variants.items():
        best_estimator, best_params, cv_score = _tune(algorithm, pipeline, X_train, y_train, cv)
        val_scores = best_estimator.predict_proba(X_val)[:, 1]
        val_pr_auc = compute_metrics(y_val, val_scores)["pr_auc"]
        results[variant_name] = {
            "estimator": best_estimator,
            "best_params": best_params,
            "cv_pr_auc": cv_score,
            "val_pr_auc": val_pr_auc,
        }
        print(f"  [{algorithm}/{variant_name}] cv_pr_auc={cv_score:.4f} val_pr_auc={val_pr_auc:.4f} params={best_params}")

    best_variant_name = max(results, key=lambda k: results[k]["val_pr_auc"])
    best = results[best_variant_name]
    best["variant"] = best_variant_name
    best["all_variants"] = {k: {"best_params": v["best_params"], "val_pr_auc": v["val_pr_auc"]} for k, v in results.items()}
    return best


def train_isolation_forest(X_train, X_val, y_val) -> dict:
    best = None
    for params in ISOLATION_FOREST_GRID:
        model = IsolationForest(random_state=RANDOM_STATE, **params)
        model.fit(X_train)
        raw_scores = -model.score_samples(X_val)  # higher = more anomalous
        scaler = MinMaxScaler()
        norm_scores = scaler.fit_transform(raw_scores.reshape(-1, 1)).ravel()
        val_pr_auc = compute_metrics(y_val, norm_scores)["pr_auc"]
        if best is None or val_pr_auc > best["val_pr_auc"]:
            best = {"model": model, "scaler": scaler, "params": params, "val_pr_auc": val_pr_auc}
        print(f"  [isolation_forest] params={params} val_pr_auc={val_pr_auc:.4f}")
    return best


def _shap_explainer_for(algorithm: str, pipeline: ImbPipeline, X_background: pd.DataFrame):
    clf = pipeline.named_steps["clf"]
    if algorithm == "logistic_regression":
        scaler = pipeline.named_steps["scaler"]
        X_bg_scaled = scaler.transform(X_background)
        explainer = shap.LinearExplainer(clf, X_bg_scaled)
        return explainer, "linear"
    explainer = shap.TreeExplainer(clf)
    return explainer, "tree"


def _predict_and_shap(algorithm: str, pipeline: ImbPipeline, explainer, explainer_kind: str, row: pd.DataFrame):
    score = float(pipeline.predict_proba(row)[:, 1][0])
    if explainer_kind == "linear":
        scaler = pipeline.named_steps["scaler"]
        row_scaled = scaler.transform(row)
        shap_values = explainer.shap_values(row_scaled)
    else:
        shap_values = explainer.shap_values(row, check_additivity=False)
        if isinstance(shap_values, list):
            shap_values = shap_values[1]
        if hasattr(shap_values, "ndim") and shap_values.ndim == 3:
            shap_values = shap_values[:, :, 1]
    return score, shap_values


def run(features_path: Path, meta_path: Path, out_dir: Path, extra_labels_path: Path | None) -> str:
    df = pd.read_parquet(features_path)
    meta = json.loads(meta_path.read_text())
    global_median_amount = meta.get("global_median_amount") or meta[list(meta.keys())[0]]["global_median_amount"]

    if extra_labels_path is not None:
        extra = pd.read_csv(extra_labels_path)
        if "label" in extra.columns and "is_fraud" not in extra.columns:
            extra = extra.rename(columns={"label": "is_fraud"})
        for col in FEATURE_NAMES:
            if col not in extra.columns:
                raise ValueError(f"--extra-labels file is missing feature column {col}")
        df = pd.concat([df, extra], ignore_index=True, sort=False)
        print(f"Appended {len(extra)} extra labelled rows from {extra_labels_path}")

    train_df, val_df, test_df = stratified_split(df)
    X_train, y_train = to_feature_matrix(train_df), train_df["is_fraud"].astype(int)
    X_val, y_val = to_feature_matrix(val_df), val_df["is_fraud"].astype(int)
    X_test, y_test = to_feature_matrix(test_df), test_df["is_fraud"].astype(int)

    cv = StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE)

    training_started = time.perf_counter()
    family_results = {}
    for algorithm in ("logistic_regression", "random_forest", "xgboost"):
        print(f"Tuning {algorithm}...")
        family_results[algorithm] = train_supervised_family(algorithm, X_train, y_train, X_val, y_val, cv)

    print("Tuning isolation_forest (unsupervised)...")
    iso_result = train_isolation_forest(X_train, X_val, y_val)
    training_time_s = time.perf_counter() - training_started

    # Model selection (Section 6.1 step 7)
    best_algorithm = max(family_results, key=lambda k: family_results[k]["val_pr_auc"])
    best_val_pr_auc = family_results[best_algorithm]["val_pr_auc"]
    for algorithm, result in family_results.items():
        if algorithm == best_algorithm:
            continue
        if abs(result["val_pr_auc"] - best_val_pr_auc) <= 0.005:
            # Within tolerance: prefer lower latency. Latency is measured below
            # only for the two competitors here.
            pass  # resolved after latency is measured

    best = family_results[best_algorithm]
    best_pipeline: ImbPipeline = best["estimator"]

    background_sample = X_train.sample(n=min(200, len(X_train)), random_state=RANDOM_STATE)
    explainer, explainer_kind = _shap_explainer_for(best_algorithm, best_pipeline, background_sample)

    def predict_one(row: pd.DataFrame):
        return _predict_and_shap(best_algorithm, best_pipeline, explainer, explainer_kind, row)

    latency_ms = measure_latency_ms(predict_one, X_test, n=1000)

    # Re-check the "within 0.005 -> prefer lower latency" tie-break properly.
    close_competitors = [
        alg for alg, res in family_results.items()
        if alg != best_algorithm and abs(res["val_pr_auc"] - best_val_pr_auc) <= 0.005
    ]
    if close_competitors:
        candidates = [best_algorithm] + close_competitors
        latencies = {}
        for alg in candidates:
            pl = family_results[alg]["estimator"]
            exp, kind = _shap_explainer_for(alg, pl, X_train.sample(n=min(200, len(X_train)), random_state=RANDOM_STATE))
            latencies[alg] = measure_latency_ms(lambda row, pl=pl, exp=exp, kind=kind: _predict_and_shap(alg, pl, exp, kind, row), X_test, n=200)
        best_algorithm = min(latencies, key=lambda a: latencies[a])
        best = family_results[best_algorithm]
        best_pipeline = best["estimator"]
        explainer, explainer_kind = _shap_explainer_for(best_algorithm, best_pipeline, X_train.sample(
            n=min(200, len(X_train)), random_state=RANDOM_STATE
        ))
        latency_ms = measure_latency_ms(predict_one, X_test, n=1000)

    test_scores = best_pipeline.predict_proba(X_test)[:, 1]
    val_scores = best_pipeline.predict_proba(X_val)[:, 1]

    test_metrics = compute_metrics(y_test, test_scores)
    val_metrics = compute_metrics(y_val, val_scores)
    metrics_at_defaults = {
        "test_at_0.40": precision_recall_at(y_test, test_scores, 0.40),
        "test_at_0.70": precision_recall_at(y_test, test_scores, 0.70),
        "val_at_0.40": precision_recall_at(y_val, val_scores, 0.40),
        "val_at_0.70": precision_recall_at(y_val, val_scores, 0.70),
    }
    suggested_thresholds = suggest_thresholds(y_val, val_scores)

    if explainer_kind == "linear":
        expected_value = float(np.ravel(explainer.expected_value)[0])
    else:
        ev = explainer.expected_value
        expected_value = float(np.ravel(ev)[-1]) if hasattr(ev, "__len__") else float(ev)

    version = f"{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M')}-{best_algorithm}"
    version_dir = out_dir / version
    version_dir.mkdir(parents=True, exist_ok=True)

    bundle = {
        "estimator": best_pipeline,
        "feature_names": FEATURE_NAMES,
        "global_median_amount": global_median_amount,
        "algorithm": best_algorithm,
        "version": version,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "suggested_thresholds": suggested_thresholds,
        "shap_expected_value": expected_value,
        "shap_explainer_kind": explainer_kind,
        "shap_background_sample": background_sample,
    }
    joblib.dump(bundle, version_dir / "model.joblib")

    metadata = {
        "algorithm": best_algorithm,
        "version": version,
        "trained_at": bundle["trained_at"],
        "training_time_seconds": training_time_s,
        "best_hyperparameters": best["best_params"],
        "chosen_variant": best["variant"],
        "family_comparison": {
            alg: {"variant": res["variant"], "val_pr_auc": res["val_pr_auc"], "all_variants": res["all_variants"]}
            for alg, res in family_results.items()
        },
        "isolation_forest_comparison": {"params": iso_result["params"], "val_pr_auc": iso_result["val_pr_auc"]},
        "validation_metrics": val_metrics,
        "test_metrics": test_metrics,
        "metrics_at_default_thresholds": metrics_at_defaults,
        "suggested_thresholds": suggested_thresholds,
        "latency_ms_per_prediction": latency_ms,
        "dataset_summary": {
            "n_train": len(train_df), "n_val": len(val_df), "n_test": len(test_df),
            "n_fraud_train": int(y_train.sum()), "n_fraud_val": int(y_val.sum()), "n_fraud_test": int(y_test.sum()),
            "global_median_amount": global_median_amount,
            "features_path": str(features_path),
            "extra_labels_path": str(extra_labels_path) if extra_labels_path else None,
        },
    }
    (version_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, default=str))

    print(f"\nSelected model: {best_algorithm} ({best['variant']} variant)")
    print(f"  val PR-AUC={best_val_pr_auc:.4f}  test PR-AUC={test_metrics['pr_auc']:.4f}  latency={latency_ms:.2f}ms")
    print(f"Saved bundle to {version_dir}")

    # Also persist the val/test split predictions for evaluate.py to reuse.
    val_df.assign(fraud_score=val_scores).to_parquet(version_dir / "val_predictions.parquet", index=False)
    test_df.assign(fraud_score=test_scores).to_parquet(version_dir / "test_predictions.parquet", index=False)

    # Persist every family's fitted model too, so evaluate.py can produce the
    # full Chapter Four comparison (Section 6.2) without retraining.
    joblib.dump(
        {
            "supervised": {alg: res["estimator"] for alg, res in family_results.items()},
            "isolation_forest": {"model": iso_result["model"], "scaler": iso_result["scaler"]},
            "selected_algorithm": best_algorithm,
        },
        version_dir / "family_models.joblib",
    )

    return version


def main() -> None:
    parser = argparse.ArgumentParser(description="Train and select the fraud detection model")
    parser.add_argument("--features", required=True, type=Path)
    parser.add_argument("--meta", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--extra-labels", default=None, type=Path)
    args = parser.parse_args()
    run(args.features, args.meta, args.out_dir, args.extra_labels)


if __name__ == "__main__":
    main()
