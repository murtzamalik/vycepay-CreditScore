"""Feature importance analysis using SHAP and XGBoost built-in methods.

Provides utilities to rank features by importance, generate SHAP summary
plots, and identify the top risk drivers for individual predictions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import shap
import xgboost as xgb

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RiskDriver:
    """A single risk driver explaining part of a credit score."""

    feature_name: str
    shap_value: float
    direction: str  # "positive" (increases risk) or "negative" (decreases risk)
    feature_value: float


def get_xgboost_importance(
    model: xgb.XGBClassifier,
    importance_type: str = "gain",
) -> pd.Series:
    """Extract feature importance from a trained XGBoost model.

    Args:
        model: Trained XGBClassifier.
        importance_type: One of 'gain', 'weight', 'cover', 'total_gain',
            'total_cover'.

    Returns:
        pd.Series of importance values indexed by feature name, sorted
        descending.
    """
    importance = model.get_booster().get_score(importance_type=importance_type)
    series = pd.Series(importance).sort_values(ascending=False)
    return series


def get_shap_importance(
    model: xgb.XGBClassifier,
    X: pd.DataFrame,
    *,
    max_samples: int = 1000,
) -> pd.DataFrame:
    """Compute global SHAP feature importance.

    Args:
        model: Trained XGBClassifier.
        X: Feature DataFrame (uses a subsample for efficiency).
        max_samples: Maximum rows to use for SHAP computation.

    Returns:
        DataFrame with columns ``feature``, ``mean_abs_shap`` sorted by
        importance descending.
    """
    if len(X) > max_samples:
        X_sample = X.sample(n=max_samples, random_state=42)
    else:
        X_sample = X

    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_sample)

    mean_abs = np.abs(shap_values).mean(axis=0)

    result = pd.DataFrame({
        "feature": X_sample.columns,
        "mean_abs_shap": mean_abs,
    }).sort_values("mean_abs_shap", ascending=False).reset_index(drop=True)

    return result


def get_top_risk_drivers(
    model: xgb.XGBClassifier,
    features: pd.DataFrame,
    *,
    top_n: int = 3,
) -> list[RiskDriver]:
    """Identify the top N risk drivers for a single prediction using SHAP.

    This powers the VyceScore Pro API's explainability output, providing
    the top 3 risk drivers with directional indicators as required by
    Kenya's Data Protection Act (DPA 2019).

    Args:
        model: Trained XGBClassifier.
        features: Single-row DataFrame with feature values.
        top_n: Number of top drivers to return.

    Returns:
        List of RiskDriver objects sorted by absolute SHAP impact.
    """
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(features)

    shap_row = shap_values[0]
    feature_values = features.iloc[0]

    # Sort by absolute SHAP value descending
    abs_shap = np.abs(shap_row)
    top_indices = np.argsort(abs_shap)[::-1][:top_n]

    drivers: list[RiskDriver] = []
    for idx in top_indices:
        feature_name = features.columns[idx]
        sv = float(shap_row[idx])
        drivers.append(RiskDriver(
            feature_name=feature_name,
            shap_value=sv,
            direction="positive" if sv > 0 else "negative",
            feature_value=float(feature_values.iloc[idx]),
        ))

    return drivers
