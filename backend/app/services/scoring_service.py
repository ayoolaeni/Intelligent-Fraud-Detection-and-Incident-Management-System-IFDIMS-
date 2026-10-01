"""Model inference + SHAP + risk band + decision (Section 8.2 steps 4-5,
Section 6.1 step 9).
"""
from __future__ import annotations

import math

from app.services.model_registry import LoadedModel
from fraud_core.constants import FEATURE_LABELS
from fraud_core.features import describe_factor, merge_hour_factors, risk_band

TOP_FACTORS_COUNT = 5


def score_and_explain(model: LoadedModel, features: dict) -> tuple[float, list[dict]]:
    """Returns (fraud_score, top_factors) where top_factors is the ordered
    list of up to :data:`TOP_FACTORS_COUNT` factors: factors that *increase*
    the score first (by descending absolute contribution), then the rest,
    also by descending absolute contribution (Section 8.2 step 4).
    """
    fraud_score, all_contributions = model.predict(features)

    hour = _hour_from_features(features)
    merged = merge_hour_factors(all_contributions, hour)

    increasing = sorted(
        (c for c in merged if c["contribution"] > 0),
        key=lambda c: -abs(c["contribution"]),
    )
    others = sorted(
        (c for c in merged if c["contribution"] <= 0),
        key=lambda c: -abs(c["contribution"]),
    )
    ordered = increasing + others
    top = ordered[:TOP_FACTORS_COUNT]

    top_factors = [
        {
            "feature": c["feature"],
            "label": FEATURE_LABELS.get(c["feature"], c["feature"]),
            "raw_value": c["raw_value"],
            "contribution": round(float(c["contribution"]), 6),
            "description": describe_factor(c["feature"], c["raw_value"]),
        }
        for c in top
    ]
    return fraud_score, top_factors


def _hour_from_features(features: dict) -> int:
    hour_sin = features.get("hour_sin")
    hour_cos = features.get("hour_cos")
    if hour_sin is None or hour_cos is None:
        return 0
    hour = round(math.atan2(hour_sin, hour_cos) * 24 / (2 * math.pi)) % 24
    return int(hour)


def band_for_score(score: float, medium_threshold: float, high_threshold: float) -> str:
    return risk_band(score, medium_threshold, high_threshold)
