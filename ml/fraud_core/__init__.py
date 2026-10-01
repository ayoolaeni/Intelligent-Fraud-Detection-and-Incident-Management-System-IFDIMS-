"""Shared fraud-scoring core: feature definitions and constants.

This package is the single source of truth for feature engineering. It is
imported both by the training pipeline (``ml/pipeline``) and by the live
backend (``backend/app/services/feature_service.py``). Do not duplicate
feature logic anywhere else.
"""

from fraud_core.constants import (
    CHANNELS,
    TXN_TYPES,
    SECURITY_EVENT_TYPES,
    FEATURE_NAMES,
    FEATURE_LABELS,
    FRAUD_TYPES,
)
from fraud_core.features import (
    compute_features_online,
    compute_features_batch,
    describe_factor,
    risk_band,
)

__all__ = [
    "CHANNELS",
    "TXN_TYPES",
    "SECURITY_EVENT_TYPES",
    "FEATURE_NAMES",
    "FEATURE_LABELS",
    "FRAUD_TYPES",
    "compute_features_online",
    "compute_features_batch",
    "describe_factor",
    "risk_band",
]
