"""Load, hot-swap and use the active fraud model (Section 8.8 activate,
Section 6.1 step 9 SHAP explainer, Section 8.2 scoring).
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
import shap
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.ml import ModelVersion
from fraud_core.constants import FEATURE_NAMES


@dataclass
class LoadedModel:
    model_id: str
    version: str
    algorithm: str
    pipeline: Any
    explainer: Any
    explainer_kind: str
    global_median_amount: float
    suggested_thresholds: dict

    def predict(self, feature_row: dict) -> tuple[float, list[dict]]:
        """Return (fraud_score, [{feature, raw_value, contribution}, ...])
        for all 23 features, unsorted (callers pick top factors)."""
        df = pd.DataFrame([{name: feature_row[name] for name in FEATURE_NAMES}])
        score = float(self.pipeline.predict_proba(df)[:, 1][0])

        if self.explainer_kind == "linear":
            scaler = self.pipeline.named_steps["scaler"]
            row_scaled = scaler.transform(df)
            shap_values = self.explainer.shap_values(row_scaled)[0]
        else:
            raw = self.explainer.shap_values(df, check_additivity=False)
            if isinstance(raw, list):
                raw = raw[1]
            if hasattr(raw, "ndim") and raw.ndim == 3:
                raw = raw[:, :, 1]
            shap_values = raw[0]

        contributions = [
            {"feature": name, "raw_value": feature_row[name], "contribution": float(shap_values[i])}
            for i, name in enumerate(FEATURE_NAMES)
        ]
        return score, contributions


class ModelRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._loaded: LoadedModel | None = None

    @property
    def loaded(self) -> LoadedModel | None:
        with self._lock:
            return self._loaded

    def _resolve_path(self, relative_path: str) -> Path:
        return Path(get_settings().models_dir) / relative_path

    def load_bundle(self, relative_path: str, model_id: str, version: str) -> LoadedModel:
        bundle_path = self._resolve_path(relative_path) / "model.joblib"
        bundle = joblib.load(bundle_path)

        if list(bundle["feature_names"]) != list(FEATURE_NAMES):
            raise RuntimeError(
                f"Model {version} feature_names do not match the active FEATURE_NAMES; refusing to load"
            )

        pipeline = bundle["estimator"]
        explainer_kind = bundle["shap_explainer_kind"]
        background = bundle["shap_background_sample"]
        clf = pipeline.named_steps["clf"]

        if explainer_kind == "linear":
            scaler = pipeline.named_steps["scaler"]
            bg_scaled = scaler.transform(background)
            explainer = shap.LinearExplainer(clf, bg_scaled)
        else:
            explainer = shap.TreeExplainer(clf)

        # Smoke prediction (Section 8.8 activate endpoint requirement).
        smoke_row = background.iloc[[0]]
        _ = pipeline.predict_proba(smoke_row)

        return LoadedModel(
            model_id=str(model_id),
            version=version,
            algorithm=bundle["algorithm"],
            pipeline=pipeline,
            explainer=explainer,
            explainer_kind=explainer_kind,
            global_median_amount=bundle["global_median_amount"],
            suggested_thresholds=bundle.get("suggested_thresholds", {}),
        )

    def load_active_from_db(self, db: Session) -> None:
        row = db.query(ModelVersion).filter(ModelVersion.is_active.is_(True)).first()
        if row is None:
            with self._lock:
                self._loaded = None
            return
        loaded = self.load_bundle(row.path, row.model_id, row.version)
        with self._lock:
            self._loaded = loaded

    def refresh_if_changed(self, db: Session) -> None:
        """Cheap per-worker check: when the backend runs as several uvicorn
        worker processes, each has its own copy of this singleton (plain
        Python module state isn't shared across processes), so activating a
        model from one request only updates the worker that handled it.
        Every worker runs this on a short interval (Section 8.8's hot-swap
        requirement must hold across all of them, not just one).
        """
        row = db.query(ModelVersion.version).filter(ModelVersion.is_active.is_(True)).first()
        current = self.loaded
        current_version = current.version if current else None
        active_version = row.version if row else None
        if current_version == active_version:
            return
        self.load_active_from_db(db)

    def activate(self, model_version_row: ModelVersion) -> LoadedModel:
        """Load and smoke-test a bundle, then hot-swap it in. Raises on any
        failure (invalid feature list, missing files, bad predict) without
        touching the currently-loaded model. The caller flips ``is_active``
        in the database in the same transaction as this call.
        """
        loaded = self.load_bundle(model_version_row.path, model_version_row.model_id, model_version_row.version)
        with self._lock:
            self._loaded = loaded
        return loaded


model_registry = ModelRegistry()
