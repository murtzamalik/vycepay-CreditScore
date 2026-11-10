"""Model serving for VyceScore API integration.

Provides thread-safe model inference with support for:
    - Single and batch predictions
    - SHAP explainability (Pro API)
    - Model hot-swapping without restart
    - MLflow model loading

This module is the bridge between the backend scoring service (FastAPI)
and the ML model.  The backend calls ModelServer methods; it never
interacts with XGBoost or SHAP directly.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import xgboost as xgb

from ml.explainability.shap_explainer import (
    ExplanationResult,
    VyceScoreExplainer,
)
from ml.scoring.converter import (
    ScoreResult,
    convert_batch,
    convert_score,
)

logger = logging.getLogger(__name__)

# Default feature columns.
CORE_FEATURES: list[str] = [
    "cblri",
    "utdi",
    "scfv",
    "ddc_ratio",
    "niq_score",
    "gos_index",
]


@dataclass(frozen=True)
class PredictionResult:
    """Result of a single model prediction.

    Attributes:
        score_result: VyceScore conversion result.
        explanation: SHAP explanation (None for Lite API).
        latency_ms: Inference latency in milliseconds.
        model_version: Version of the model used.
    """

    score_result: ScoreResult
    explanation: ExplanationResult | None
    latency_ms: float
    model_version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to a JSON-serializable dict."""
        result = self.score_result.to_dict()
        result["latency_ms"] = round(self.latency_ms, 2)
        if self.model_version:
            result["model_version"] = self.model_version
        if self.explanation:
            result["risk_drivers"] = [
                {
                    "factor": d.factor,
                    "impact": d.impact,
                    "description": d.description,
                    "contribution": d.contribution,
                }
                for d in self.explanation.risk_drivers
            ]
        return result


@dataclass(frozen=True)
class BatchPredictionResult:
    """Result of a batch model prediction.

    Attributes:
        results: List of ScoreResult for each input row.
        latency_ms: Total batch inference latency in milliseconds.
        model_version: Version of the model used.
    """

    results: list[ScoreResult]
    latency_ms: float
    model_version: str | None = None


class ModelServer:
    """Thread-safe model server for VyceScore inference.

    Supports loading models from disk (XGBoost JSON) or MLflow,
    hot-swapping models without restart, and concurrent predictions.

    Usage:
        server = ModelServer()
        server.load_model_from_file("model.json")

        # Lite API (score only)
        result = server.predict(features_df)

        # Pro API (score + SHAP)
        result = server.predict(features_df, explain=True)

        # Hot-swap to new model
        server.load_model_from_file("model_v2.json")
    """

    def __init__(
        self,
        feature_columns: list[str] | None = None,
    ) -> None:
        """Initialize the model server.

        Args:
            feature_columns: Feature column names. Defaults to CORE_FEATURES.
        """
        self._feature_columns = feature_columns or list(CORE_FEATURES)
        self._model: xgb.XGBClassifier | None = None
        self._explainer: VyceScoreExplainer | None = None
        self._model_version: str | None = None
        self._lock = threading.RLock()
        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        """Whether a model is currently loaded."""
        return self._loaded

    @property
    def model_version(self) -> str | None:
        """Current model version identifier."""
        return self._model_version

    @property
    def feature_columns(self) -> list[str]:
        """Feature columns used by the model."""
        return list(self._feature_columns)

    def load_model_from_file(
        self,
        model_path: str,
        *,
        version: str | None = None,
    ) -> None:
        """Load a model from an XGBoost JSON file.

        Thread-safe: acquires a write lock before swapping.

        Args:
            model_path: Path to the XGBoost model file (.json or .ubj).
            version: Optional version identifier.

        Raises:
            FileNotFoundError: If model file does not exist.
            RuntimeError: If model loading fails.
        """
        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")

        try:
            model = xgb.XGBClassifier()
            model.load_model(str(path))
            explainer = VyceScoreExplainer(model)

            with self._lock:
                self._model = model
                self._explainer = explainer
                self._model_version = version
                self._loaded = True

            logger.info(
                "Model loaded from %s (version=%s)",
                model_path,
                version,
            )
        except Exception as e:
            raise RuntimeError(f"Failed to load model from {model_path}: {e}") from e

    def load_model_from_mlflow(
        self,
        model_uri: str = "models:/vycescore-xgboost/Production",
        *,
        version: str | None = None,
    ) -> None:
        """Load a model from MLflow model registry.

        Args:
            model_uri: MLflow model URI.
            version: Optional version identifier.

        Raises:
            RuntimeError: If model loading fails.
        """
        try:
            import mlflow.xgboost

            model = mlflow.xgboost.load_model(model_uri)
            explainer = VyceScoreExplainer(model)

            with self._lock:
                self._model = model
                self._explainer = explainer
                self._model_version = version
                self._loaded = True

            logger.info(
                "Model loaded from MLflow: %s (version=%s)",
                model_uri,
                version,
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to load model from MLflow ({model_uri}): {e}"
            ) from e

    def load_model_direct(
        self,
        model: xgb.XGBClassifier,
        *,
        version: str | None = None,
    ) -> None:
        """Load a pre-trained model directly.

        Useful for testing or when the model is already in memory.

        Args:
            model: Trained XGBoost classifier.
            version: Optional version identifier.
        """
        explainer = VyceScoreExplainer(model)

        with self._lock:
            self._model = model
            self._explainer = explainer
            self._model_version = version
            self._loaded = True

        logger.info("Model loaded directly (version=%s)", version)

    def predict(
        self,
        features: pd.DataFrame,
        *,
        explain: bool = False,
        top_n_drivers: int = 3,
        include_confidence: bool = False,
    ) -> PredictionResult:
        """Make a single prediction.

        Args:
            features: Single-row DataFrame with feature values.
            explain: If True, include SHAP explanation (Pro API).
            top_n_drivers: Number of top risk drivers for SHAP.
            include_confidence: Whether to include confidence interval.

        Returns:
            PredictionResult with score and optional explanation.

        Raises:
            RuntimeError: If no model is loaded.
            ValueError: If features DataFrame is empty or has wrong shape.
        """
        if not self._loaded:
            raise RuntimeError("No model loaded. Call load_model_* first.")

        if len(features) == 0:
            raise ValueError("Empty features DataFrame")

        if len(features) > 1:
            raise ValueError(
                f"Expected single row, got {len(features)}. "
                f"Use predict_batch for multiple predictions."
            )

        start = time.perf_counter()

        with self._lock:
            model = self._model
            explainer = self._explainer
            version = self._model_version

        assert model is not None
        assert explainer is not None

        # Get feature subset
        X = features[self._feature_columns]

        # Predict probability
        prob = float(model.predict_proba(X)[:, 1][0])

        # Convert to score
        score_result = convert_score(
            prob, include_confidence=include_confidence
        )

        # SHAP explanation (Pro API only)
        explanation: ExplanationResult | None = None
        if explain:
            explanation = explainer.explain(X, top_n=top_n_drivers)

        latency_ms = (time.perf_counter() - start) * 1000

        return PredictionResult(
            score_result=score_result,
            explanation=explanation,
            latency_ms=latency_ms,
            model_version=version,
        )

    def predict_batch(
        self,
        features: pd.DataFrame,
        *,
        include_confidence: bool = False,
    ) -> BatchPredictionResult:
        """Make batch predictions (without SHAP explanations).

        For efficiency, batch predictions do not include SHAP explanations.
        Use predict() with explain=True for individual explanations.

        Args:
            features: Multi-row DataFrame with feature values.
            include_confidence: Whether to include confidence intervals.

        Returns:
            BatchPredictionResult with scores for each row.

        Raises:
            RuntimeError: If no model is loaded.
            ValueError: If features DataFrame is empty.
        """
        if not self._loaded:
            raise RuntimeError("No model loaded. Call load_model_* first.")

        if len(features) == 0:
            raise ValueError("Empty features DataFrame")

        start = time.perf_counter()

        with self._lock:
            model = self._model
            version = self._model_version

        assert model is not None

        X = features[self._feature_columns]
        probabilities = model.predict_proba(X)[:, 1]

        results = convert_batch(
            probabilities, include_confidence=include_confidence
        )

        latency_ms = (time.perf_counter() - start) * 1000

        return BatchPredictionResult(
            results=results,
            latency_ms=latency_ms,
            model_version=version,
        )

    def health_check(self) -> dict[str, Any]:
        """Return model server health status.

        Returns:
            Dict with server status information.
        """
        return {
            "status": "healthy" if self._loaded else "no_model_loaded",
            "model_loaded": self._loaded,
            "model_version": self._model_version,
            "feature_columns": self._feature_columns,
        }
