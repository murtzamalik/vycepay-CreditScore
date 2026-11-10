"""VyceScore model serving service.

Provides the VyceScorePredictor class that powers both the Lite API
(score + NIQ only, <500ms) and Pro API (score + top 3 SHAP risk drivers, <2s).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import mlflow.xgboost
import numpy as np
import pandas as pd
import shap
import xgboost as xgb

from ml.features.selection.importance import RiskDriver, get_top_risk_drivers
from ml.models.xgboost.hyperparams import CORE_FEATURES
from ml.models.xgboost.predict import probability_to_score

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LiteResult:
    """Response payload for VyceScore Lite API."""

    national_id: str
    vyce_score: int  # 300-900
    niq_score: float  # 0-100
    probability: float
    latency_ms: float


@dataclass(frozen=True)
class ProResult:
    """Response payload for VyceScore Pro API."""

    national_id: str
    vyce_score: int  # 300-900
    niq_score: float  # 0-100
    probability: float
    risk_drivers: list[dict[str, Any]]  # Top 3 SHAP-based explanations
    latency_ms: float


class VyceScorePredictor:
    """Model serving class that handles both Lite and Pro predictions.

    Loads the model and SHAP explainer once at initialization, then
    serves predictions with minimal latency.

    Usage:
        predictor = VyceScorePredictor()
        lite = predictor.predict_lite("12345678", features_df)
        pro = predictor.predict_pro("12345678", features_df)
    """

    def __init__(
        self,
        model_uri: str = "models:/vycescore-xgboost/Production",
        feature_columns: list[str] | None = None,
        preload: bool = True,
    ) -> None:
        """Initialize the predictor.

        Args:
            model_uri: MLflow model URI for the production model.
            feature_columns: Feature column names. Falls back to CORE_FEATURES.
            preload: If True, load the model immediately. Set False for
                lazy loading (useful in tests).
        """
        self.model_uri = model_uri
        self.feature_columns = feature_columns or CORE_FEATURES
        self._model: xgb.XGBClassifier | None = None
        self._explainer: shap.TreeExplainer | None = None

        if preload:
            self._load_model()

    def _load_model(self) -> None:
        """Load the model and initialize the SHAP explainer."""
        logger.info("Loading model from %s", self.model_uri)
        self._model = mlflow.xgboost.load_model(self.model_uri)
        self._explainer = shap.TreeExplainer(self._model)
        logger.info("Model and SHAP explainer loaded successfully")

    @property
    def model(self) -> xgb.XGBClassifier:
        if self._model is None:
            self._load_model()
        assert self._model is not None
        return self._model

    @property
    def explainer(self) -> shap.TreeExplainer:
        if self._explainer is None:
            self._load_model()
        assert self._explainer is not None
        return self._explainer

    def predict_lite(
        self,
        national_id: str,
        features: pd.DataFrame,
    ) -> LiteResult:
        """Generate a VyceScore Lite prediction.

        Returns the VyceScore and NIQ Score only — no SHAP explanations.
        Target latency: <500ms.

        Args:
            national_id: Kenyan national ID of the entity.
            features: Single-row DataFrame with the six core features.

        Returns:
            LiteResult with score, NIQ, and probability.
        """
        start = time.perf_counter()

        X = features[self.feature_columns]
        prob = float(self.model.predict_proba(X)[:, 1][0])
        score = probability_to_score(prob)
        niq = float(features["niq_score"].iloc[0])

        latency_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "Lite prediction for %s: score=%d, niq=%.1f, latency=%.1fms",
            national_id, score, niq, latency_ms,
        )

        return LiteResult(
            national_id=national_id,
            vyce_score=score,
            niq_score=niq,
            probability=prob,
            latency_ms=round(latency_ms, 2),
        )

    def predict_pro(
        self,
        national_id: str,
        features: pd.DataFrame,
        *,
        top_n_drivers: int = 3,
    ) -> ProResult:
        """Generate a VyceScore Pro prediction with SHAP explanations.

        Returns the VyceScore, NIQ Score, and top N risk drivers with
        directional indicators. Satisfies Kenya DPA 2019 requirement for
        "meaningful information about the logic involved" in automated
        decisions. Target latency: <2s.

        Args:
            national_id: Kenyan national ID of the entity.
            features: Single-row DataFrame with the six core features.
            top_n_drivers: Number of top risk drivers to return.

        Returns:
            ProResult with score, NIQ, probability, and risk drivers.
        """
        start = time.perf_counter()

        X = features[self.feature_columns]
        prob = float(self.model.predict_proba(X)[:, 1][0])
        score = probability_to_score(prob)
        niq = float(features["niq_score"].iloc[0])

        # SHAP explanation
        drivers = get_top_risk_drivers(
            self.model, features[self.feature_columns], top_n=top_n_drivers
        )

        risk_drivers = [
            {
                "feature": d.feature_name,
                "impact": round(d.shap_value, 4),
                "direction": d.direction,
                "value": round(d.feature_value, 4),
            }
            for d in drivers
        ]

        latency_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "Pro prediction for %s: score=%d, niq=%.1f, drivers=%d, latency=%.1fms",
            national_id, score, niq, len(risk_drivers), latency_ms,
        )

        return ProResult(
            national_id=national_id,
            vyce_score=score,
            niq_score=niq,
            probability=prob,
            risk_drivers=risk_drivers,
            latency_ms=round(latency_ms, 2),
        )
