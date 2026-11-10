"""Canary deployment for gradual VyceScore model rollout.

Routes a configurable percentage of traffic to a new candidate model
while the rest continues using the production model.  Tracks per-model
metrics and supports automatic rollback if error rates exceed a threshold.

Usage:
    canary = CanaryDeployment(
        production_model=prod,
        candidate_model=cand,
        traffic_percentage=5.0,
    )
    result = canary.predict(features)
    # result.model_used indicates which model served the prediction
"""

from __future__ import annotations

import logging
import random
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd
import xgboost as xgb

logger = logging.getLogger(__name__)

MAX_METRIC_WINDOW = 5_000


@dataclass(frozen=True)
class CanaryConfig:
    """Configuration for canary deployment.

    Attributes:
        traffic_percentage: Percentage of traffic routed to candidate (0-100).
        error_rate_threshold: Maximum error rate before auto-rollback.
        latency_threshold_ms: Maximum p95 latency before auto-rollback.
        min_predictions_before_rollback: Minimum predictions before auto-
            rollback logic activates.
        auto_rollback: Whether to automatically rollback on threshold breach.
    """

    traffic_percentage: float = 5.0
    error_rate_threshold: float = 0.05
    latency_threshold_ms: float = 2000.0
    min_predictions_before_rollback: int = 100
    auto_rollback: bool = True


@dataclass(frozen=True)
class CanaryPrediction:
    """Result from a canary deployment prediction.

    Attributes:
        probability: Predicted probability of default.
        score: VyceScore (300-900).
        model_used: Which model served this prediction (production/candidate).
        model_version: Version string of the model used.
        latency_ms: Prediction latency in milliseconds.
    """

    probability: float
    score: int
    model_used: str
    model_version: str | None
    latency_ms: float


@dataclass
class CanaryMetrics:
    """Per-model metrics tracked during canary deployment.

    Attributes:
        model_id: Identifier for the model (production/candidate).
        total_predictions: Total predictions served.
        total_errors: Total prediction errors.
        error_rate: Error rate (errors / predictions).
        mean_latency_ms: Mean prediction latency.
        p95_latency_ms: 95th percentile latency.
        mean_probability: Mean predicted probability.
    """

    model_id: str = ""
    total_predictions: int = 0
    total_errors: int = 0
    error_rate: float = 0.0
    mean_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    mean_probability: float = 0.0


class CanaryDeployment:
    """Canary deployment manager for gradual model rollout.

    Thread-safe. Routes requests probabilistically between production
    and candidate models.

    Args:
        production_model: Currently deployed model.
        candidate_model: New model to canary test.
        config: Canary deployment configuration.
        production_version: Version string for production model.
        candidate_version: Version string for candidate model.
        feature_columns: Feature column names.
    """

    def __init__(
        self,
        production_model: xgb.XGBClassifier,
        candidate_model: xgb.XGBClassifier,
        config: CanaryConfig | None = None,
        production_version: str | None = None,
        candidate_version: str | None = None,
        feature_columns: list[str] | None = None,
    ) -> None:
        from ml.training.pipeline import CORE_FEATURES

        self._production = production_model
        self._candidate = candidate_model
        self._config = config or CanaryConfig()
        self._production_version = production_version
        self._candidate_version = candidate_version
        self._feature_columns = feature_columns or list(CORE_FEATURES)
        self._lock = threading.Lock()
        self._active = True
        self._rolled_back = False

        # Per-model metric tracking
        self._prod_latencies: deque[float] = deque(maxlen=MAX_METRIC_WINDOW)
        self._cand_latencies: deque[float] = deque(maxlen=MAX_METRIC_WINDOW)
        self._prod_probs: deque[float] = deque(maxlen=MAX_METRIC_WINDOW)
        self._cand_probs: deque[float] = deque(maxlen=MAX_METRIC_WINDOW)
        self._prod_predictions = 0
        self._cand_predictions = 0
        self._prod_errors = 0
        self._cand_errors = 0

        logger.info(
            "Canary deployment started: %.1f%% traffic to candidate "
            "(version: %s).",
            self._config.traffic_percentage,
            candidate_version,
        )

    @property
    def is_active(self) -> bool:
        """Whether canary deployment is currently active."""
        return self._active

    @property
    def is_rolled_back(self) -> bool:
        """Whether the candidate has been rolled back."""
        return self._rolled_back

    @property
    def traffic_percentage(self) -> float:
        """Current traffic percentage routed to candidate."""
        return self._config.traffic_percentage

    def set_traffic_percentage(self, percentage: float) -> None:
        """Update the traffic percentage routed to candidate.

        Args:
            percentage: New percentage (0-100).
        """
        if not 0.0 <= percentage <= 100.0:
            raise ValueError("Traffic percentage must be between 0 and 100")

        self._config = CanaryConfig(
            traffic_percentage=percentage,
            error_rate_threshold=self._config.error_rate_threshold,
            latency_threshold_ms=self._config.latency_threshold_ms,
            min_predictions_before_rollback=self._config.min_predictions_before_rollback,
            auto_rollback=self._config.auto_rollback,
        )
        logger.info("Canary traffic updated to %.1f%%.", percentage)

    def predict(
        self,
        features: pd.DataFrame,
    ) -> CanaryPrediction:
        """Make a prediction using either production or candidate model.

        Traffic routing is probabilistic based on ``traffic_percentage``.

        Args:
            features: Single-row DataFrame with feature values.

        Returns:
            CanaryPrediction with the result and model identifier.
        """
        if self._rolled_back or not self._active:
            return self._predict_production(features)

        # Probabilistic routing
        use_candidate = random.random() * 100 < self._config.traffic_percentage

        if use_candidate:
            result = self._predict_candidate(features)
        else:
            result = self._predict_production(features)

        # Check auto-rollback conditions
        if self._config.auto_rollback:
            self._check_rollback()

        return result

    def get_metrics(self) -> dict[str, CanaryMetrics]:
        """Get current metrics for both production and candidate models.

        Returns:
            Dict with 'production' and 'candidate' CanaryMetrics.
        """
        with self._lock:
            prod_metrics = self._compute_metrics(
                "production",
                self._prod_predictions,
                self._prod_errors,
                list(self._prod_latencies),
                list(self._prod_probs),
            )
            cand_metrics = self._compute_metrics(
                "candidate",
                self._cand_predictions,
                self._cand_errors,
                list(self._cand_latencies),
                list(self._cand_probs),
            )

        return {
            "production": prod_metrics,
            "candidate": cand_metrics,
        }

    def promote_candidate(self) -> None:
        """Promote the candidate to production (100% traffic).

        After promotion, all traffic goes to the candidate model.
        """
        self.set_traffic_percentage(100.0)
        self._active = False
        logger.info(
            "Candidate (version %s) promoted to production.",
            self._candidate_version,
        )

    def rollback(self, reason: str = "manual") -> None:
        """Rollback: route all traffic to production model.

        Args:
            reason: Reason for the rollback.
        """
        self._rolled_back = True
        self._active = False
        logger.warning(
            "Canary ROLLBACK triggered (reason: %s). All traffic "
            "routed to production model.",
            reason,
        )

    def stop(self) -> dict[str, CanaryMetrics]:
        """Stop canary deployment and return final metrics."""
        self._active = False
        metrics = self.get_metrics()
        logger.info("Canary deployment stopped.")
        return metrics

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _predict_production(self, features: pd.DataFrame) -> CanaryPrediction:
        """Run prediction through the production model."""
        start = time.perf_counter()
        try:
            X = features[self._feature_columns]
            prob = float(self._production.predict_proba(X)[:, 1][0])
            latency_ms = (time.perf_counter() - start) * 1000

            with self._lock:
                self._prod_predictions += 1
                self._prod_latencies.append(latency_ms)
                self._prod_probs.append(prob)

            return CanaryPrediction(
                probability=prob,
                score=_prob_to_score(prob),
                model_used="production",
                model_version=self._production_version,
                latency_ms=latency_ms,
            )
        except Exception:
            with self._lock:
                self._prod_predictions += 1
                self._prod_errors += 1
            raise

    def _predict_candidate(self, features: pd.DataFrame) -> CanaryPrediction:
        """Run prediction through the candidate model."""
        start = time.perf_counter()
        try:
            X = features[self._feature_columns]
            prob = float(self._candidate.predict_proba(X)[:, 1][0])
            latency_ms = (time.perf_counter() - start) * 1000

            with self._lock:
                self._cand_predictions += 1
                self._cand_latencies.append(latency_ms)
                self._cand_probs.append(prob)

            return CanaryPrediction(
                probability=prob,
                score=_prob_to_score(prob),
                model_used="candidate",
                model_version=self._candidate_version,
                latency_ms=latency_ms,
            )
        except Exception:
            with self._lock:
                self._cand_predictions += 1
                self._cand_errors += 1
            raise

    def _check_rollback(self) -> None:
        """Check if auto-rollback conditions are met for the candidate."""
        with self._lock:
            if self._cand_predictions < self._config.min_predictions_before_rollback:
                return

            if self._cand_predictions == 0:
                return

            error_rate = self._cand_errors / self._cand_predictions

            if error_rate > self._config.error_rate_threshold:
                self.rollback(
                    reason=f"error_rate={error_rate:.4f} > "
                    f"{self._config.error_rate_threshold}"
                )
                return

            if self._cand_latencies:
                p95 = float(np.percentile(list(self._cand_latencies), 95))
                if p95 > self._config.latency_threshold_ms:
                    self.rollback(
                        reason=f"p95_latency={p95:.0f}ms > "
                        f"{self._config.latency_threshold_ms}ms"
                    )

    @staticmethod
    def _compute_metrics(
        model_id: str,
        total_predictions: int,
        total_errors: int,
        latencies: list[float],
        probabilities: list[float],
    ) -> CanaryMetrics:
        """Compute metrics for a single model."""
        error_rate = (
            total_errors / total_predictions if total_predictions > 0 else 0.0
        )
        mean_latency = float(np.mean(latencies)) if latencies else 0.0
        p95_latency = float(np.percentile(latencies, 95)) if latencies else 0.0
        mean_prob = float(np.mean(probabilities)) if probabilities else 0.0

        return CanaryMetrics(
            model_id=model_id,
            total_predictions=total_predictions,
            total_errors=total_errors,
            error_rate=error_rate,
            mean_latency_ms=mean_latency,
            p95_latency_ms=p95_latency,
            mean_probability=mean_prob,
        )


def _prob_to_score(probability: float) -> int:
    """Convert probability to VyceScore (300-900)."""
    score = 300 + int((1.0 - probability) * 600)
    return max(300, min(900, score))
