"""Industry-specific model variants for Deep Dive API.

Provides different feature weight profiles per industry vertical:
    - Retail
    - Manufacturing
    - Services
    - Agriculture

Each variant adjusts the relative importance of the six core features
to reflect industry-specific risk patterns.  For example, agricultural
businesses have higher Geographic Operational Stability importance,
while manufacturing businesses weight Supply Chain Formalization Velocity
more heavily.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd
import xgboost as xgb

logger = logging.getLogger(__name__)

# Core features in canonical order
CORE_FEATURES: list[str] = [
    "cblri",
    "utdi",
    "scfv",
    "ddc_ratio",
    "niq_score",
    "gos_index",
]


class IndustryVertical(str, Enum):
    """Supported industry verticals."""

    GENERAL = "general"
    RETAIL = "retail"
    MANUFACTURING = "manufacturing"
    SERVICES = "services"
    AGRICULTURE = "agriculture"


@dataclass(frozen=True)
class IndustryProfile:
    """Feature weight profile for an industry vertical.

    Attributes:
        vertical: Industry vertical identifier.
        feature_weights: Relative importance weights for each feature.
            Values are multipliers applied to feature values before scoring.
        description: Human-readable description of the profile.
        min_training_samples: Minimum samples required for a dedicated
            industry model (falls back to general otherwise).
        prediction_horizons: Supported prediction horizons in days.
    """

    vertical: IndustryVertical
    feature_weights: dict[str, float]
    description: str
    min_training_samples: int = 1000
    prediction_horizons: tuple[int, ...] = (30, 90, 365)


# Industry profiles with calibrated feature weight adjustments.
INDUSTRY_PROFILES: dict[IndustryVertical, IndustryProfile] = {
    IndustryVertical.GENERAL: IndustryProfile(
        vertical=IndustryVertical.GENERAL,
        feature_weights={
            "cblri": 1.0,
            "utdi": 1.0,
            "scfv": 1.0,
            "ddc_ratio": 1.0,
            "niq_score": 1.0,
            "gos_index": 1.0,
        },
        description="General model with equal feature weighting.",
    ),
    IndustryVertical.RETAIL: IndustryProfile(
        vertical=IndustryVertical.RETAIL,
        feature_weights={
            "cblri": 1.0,
            "utdi": 1.3,       # Merchant diversity is critical for retail
            "scfv": 0.8,
            "ddc_ratio": 1.0,
            "niq_score": 1.2,  # Network quality matters for retail
            "gos_index": 0.9,
        },
        description="Retail: emphasises transaction diversity and network quality.",
    ),
    IndustryVertical.MANUFACTURING: IndustryProfile(
        vertical=IndustryVertical.MANUFACTURING,
        feature_weights={
            "cblri": 1.1,
            "utdi": 0.9,
            "scfv": 1.4,       # Supply chain formalisation is key
            "ddc_ratio": 1.1,
            "niq_score": 1.0,
            "gos_index": 0.8,
        },
        description="Manufacturing: emphasises supply chain formalisation.",
    ),
    IndustryVertical.SERVICES: IndustryProfile(
        vertical=IndustryVertical.SERVICES,
        feature_weights={
            "cblri": 1.2,      # Cash flow consistency matters
            "utdi": 1.1,
            "scfv": 0.7,       # Less relevant for service businesses
            "ddc_ratio": 1.2,
            "niq_score": 1.1,
            "gos_index": 0.9,
        },
        description="Services: emphasises cash flow consistency and compliance.",
    ),
    IndustryVertical.AGRICULTURE: IndustryProfile(
        vertical=IndustryVertical.AGRICULTURE,
        feature_weights={
            "cblri": 0.9,
            "utdi": 0.8,
            "scfv": 1.1,
            "ddc_ratio": 0.9,
            "niq_score": 0.8,
            "gos_index": 1.5,  # Geographic stability is critical
        },
        description="Agriculture: emphasises geographic operational stability.",
    ),
}


def get_industry_profile(vertical: IndustryVertical | str) -> IndustryProfile:
    """Get the industry profile for a vertical.

    Args:
        vertical: Industry vertical name or enum value.

    Returns:
        IndustryProfile for the requested vertical.

    Raises:
        ValueError: If the vertical is not supported.
    """
    if isinstance(vertical, str):
        try:
            vertical = IndustryVertical(vertical.lower())
        except ValueError:
            raise ValueError(
                f"Unsupported industry vertical: {vertical}. "
                f"Supported: {[v.value for v in IndustryVertical]}"
            )

    profile = INDUSTRY_PROFILES.get(vertical)
    if profile is None:
        raise ValueError(f"No profile defined for vertical: {vertical}")

    return profile


def apply_industry_weights(
    features: pd.DataFrame,
    vertical: IndustryVertical | str,
) -> pd.DataFrame:
    """Apply industry-specific feature weights to a feature DataFrame.

    Multiplies each feature column by the industry-specific weight,
    producing an adjusted feature set for scoring.

    Args:
        features: DataFrame with core feature columns.
        vertical: Industry vertical to apply.

    Returns:
        DataFrame with weighted feature values.
    """
    profile = get_industry_profile(vertical)
    weighted = features.copy()

    for col, weight in profile.feature_weights.items():
        if col in weighted.columns:
            weighted[col] = weighted[col] * weight

    return weighted


def get_prediction_horizon_config(
    horizon_days: int,
) -> dict[str, Any]:
    """Get configuration adjustments for a specific prediction horizon.

    Shorter horizons focus more on recent features; longer horizons
    weight historical patterns more heavily.

    Args:
        horizon_days: Prediction horizon in days (30, 90, or 365).

    Returns:
        Dict with horizon-specific configuration.
    """
    if horizon_days not in (30, 90, 365):
        raise ValueError(
            f"Unsupported prediction horizon: {horizon_days} days. "
            f"Supported: 30, 90, 365."
        )

    configs: dict[int, dict[str, Any]] = {
        30: {
            "horizon_days": 30,
            "horizon_label": "30_days",
            "description": "Short-term risk assessment (30 days)",
            "score_interpretation": "Probability of payment issues within 30 days",
            "recency_weight": 1.5,  # More weight on recent features
        },
        90: {
            "horizon_days": 90,
            "horizon_label": "90_days",
            "description": "Medium-term risk assessment (90 days)",
            "score_interpretation": "Probability of delinquency within 90 days",
            "recency_weight": 1.2,
        },
        365: {
            "horizon_days": 365,
            "horizon_label": "12_months",
            "description": "Standard annual risk assessment (12 months)",
            "score_interpretation": (
                "Probability of Serious Delinquency (90+ DPD) within 12 months"
            ),
            "recency_weight": 1.0,
        },
    }

    return configs[horizon_days]


def list_supported_verticals() -> list[dict[str, Any]]:
    """List all supported industry verticals with their descriptions.

    Returns:
        List of dicts with vertical info.
    """
    return [
        {
            "vertical": profile.vertical.value,
            "description": profile.description,
            "prediction_horizons": list(profile.prediction_horizons),
            "min_training_samples": profile.min_training_samples,
        }
        for profile in INDUSTRY_PROFILES.values()
    ]
