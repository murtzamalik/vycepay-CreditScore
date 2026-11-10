"""Prediction functions for VyceScore XGBoost model.

Loads a trained model from MLflow and returns a VyceScore (300-900)
along with the raw delinquency probability.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import mlflow.xgboost
import numpy as np
import pandas as pd

from ml.models.xgboost.hyperparams import CORE_FEATURES

logger = logging.getLogger(__name__)

SCORE_MIN = 300
SCORE_MAX = 900
SCORE_RANGE = SCORE_MAX - SCORE_MIN  # 600


@dataclass(frozen=True)
class ScorePrediction:
    """Result of a VyceScore prediction."""

    score: int  # 300-900, higher = lower risk
    probability: float  # P(90+ DPD within 12 months)
    national_id: str | None = None


def probability_to_score(probability: float) -> int:
    """Convert delinquency probability to a VyceScore (300-900).

    Formula: score = 300 + (1 - probability) * 600
    A probability of 0.0 yields 900 (lowest risk).
    A probability of 1.0 yields 300 (highest risk).
    """
    score = SCORE_MIN + (1.0 - probability) * SCORE_RANGE
    return int(np.clip(round(score), SCORE_MIN, SCORE_MAX))


def load_model(model_uri: str = "models:/vycescore-xgboost/Production"):
    """Load a trained XGBoost model from MLflow model registry.

    Args:
        model_uri: MLflow model URI. Defaults to the Production stage
            of the ``vycescore-xgboost`` registered model.

    Returns:
        Loaded XGBoost model ready for inference.
    """
    logger.info("Loading model from %s", model_uri)
    model = mlflow.xgboost.load_model(model_uri)
    return model


def predict_score(
    features: pd.DataFrame,
    *,
    model=None,
    model_uri: str = "models:/vycescore-xgboost/Production",
    feature_columns: list[str] | None = None,
    national_id: str | None = None,
) -> ScorePrediction:
    """Predict a VyceScore for a single entity.

    Args:
        features: DataFrame with one row containing the six core features.
        model: Pre-loaded model. If None, loads from ``model_uri``.
        model_uri: MLflow model URI (used only when ``model`` is None).
        feature_columns: Feature column names. Falls back to CORE_FEATURES.
        national_id: Optional national ID attached to the result.

    Returns:
        ScorePrediction with score (300-900) and raw probability.
    """
    if model is None:
        model = load_model(model_uri)

    cols = feature_columns or CORE_FEATURES
    X = features[cols]

    probabilities = model.predict_proba(X)[:, 1]
    prob = float(probabilities[0])
    score = probability_to_score(prob)

    logger.info(
        "Prediction for %s: score=%d, probability=%.4f",
        national_id or "unknown",
        score,
        prob,
    )

    return ScorePrediction(score=score, probability=prob, national_id=national_id)


def predict_batch(
    features: pd.DataFrame,
    *,
    model=None,
    model_uri: str = "models:/vycescore-xgboost/Production",
    feature_columns: list[str] | None = None,
) -> pd.DataFrame:
    """Predict VyceScores for a batch of entities.

    Args:
        features: DataFrame with N rows and the six core features.
        model: Pre-loaded model. If None, loads from ``model_uri``.
        model_uri: MLflow model URI (used only when ``model`` is None).
        feature_columns: Feature column names. Falls back to CORE_FEATURES.

    Returns:
        DataFrame with columns ``probability`` and ``score``.
    """
    if model is None:
        model = load_model(model_uri)

    cols = feature_columns or CORE_FEATURES
    X = features[cols]

    probabilities = model.predict_proba(X)[:, 1]
    scores = np.array([probability_to_score(p) for p in probabilities])

    return pd.DataFrame({
        "probability": probabilities,
        "score": scores,
    }, index=features.index)
