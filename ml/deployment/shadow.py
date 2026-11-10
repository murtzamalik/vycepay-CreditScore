"""Shadow mode deployment for VyceScore model validation.

Runs a new candidate model in parallel with the production model,
logging predictions from both without affecting live scores.  This
allows comparison of prediction distributions and detection of
issues before any traffic is routed to the candidate.

Usage:
    shadow = ShadowDeployment(production_model, candidate_model)
    result = shadow.predict(features)
    # result.production is used for the actual response
    # result.candidate is logged for comparison
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd
import xgboost as xgb

logger = logging.getLogger(__name__)

# Maximum number of comparison records to keep in memory.
MAX_COMPARISON_BUFFER = 10_000


@dataclass(frozen=True)
class ShadowPrediction:
    """A single shadow comparison between production and candidate."""

    production_probability: float
    candidate_probability: float
    production_score: int
    candidate_score: int
    delta_probability: float
    delta_score: int
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class ShadowComparisonSummary:
    """Summary statistics from shadow mode comparisons.

    Attributes:
        n_predictions: Total number of shadow predictions made.
        mean_probability_delta: Average difference in predicted probabilities.
        std_probability_delta: Standard deviation of probability deltas.
        mean_score_delta: Average difference in VyceScore points.
        correlation: Pearson correlation between production and candidate
            predicted probabilities.
        production_mean_prob: Mean production model probability.
        candidate_mean_prob: Mean candidate model probability.
        max_absolute_delta: Maximum absolute probability difference.
    """

    n_predictions: int = 0
    mean_probability_delta: float = 0.0
    std_probability_delta: float = 0.0
    mean_score_delta: float = 0.0
    correlation: float = 0.0
    production_mean_prob: float = 0.0
    candidate_mean_prob: float = 0.0
    max_absolute_delta: float = 0.0


class ShadowDeployment:
    """Run a candidate model in shadow mode alongside production.

    Thread-safe.  All candidate predictions are logged but never used
    for actual scoring responses.

    Args:
        production_model: The currently deployed XGBoost model.
        candidate_model: The candidate model to evaluate.
        feature_columns: Feature column names.
        candidate_version: Version string for the candidate model.
    """

    def __init__(
        self,
        production_model: xgb.XGBClassifier,
        candidate_model: xgb.XGBClassifier,
        feature_columns: list[str] | None = None,
        candidate_version: str | None = None,
    ) -> None:
        from ml.training.pipeline import CORE_FEATURES

        self._production = production_model
        self._candidate = candidate_model
        self._feature_columns = feature_columns or list(CORE_FEATURES)
        self._candidate_version = candidate_version
        self._comparisons: deque[ShadowPrediction] = deque(maxlen=MAX_COMPARISON_BUFFER)
        self._lock = threading.Lock()
        self._active = True

        logger.info(
            "Shadow deployment started (candidate version: %s).",
            candidate_version,
        )

    @property
    def is_active(self) -> bool:
        """Whether shadow mode is currently active."""
        return self._active

    @property
    def comparison_count(self) -> int:
        """Number of shadow comparisons recorded."""
        return len(self._comparisons)

    def predict(
        self,
        features: pd.DataFrame,
    ) -> ShadowPrediction:
        """Run both models on the same input and record the comparison.

        Args:
            features: Single-row DataFrame with feature values.

        Returns:
            ShadowPrediction with both models' outputs.

        Note:
            The production prediction is always the one used for the
            live response.  The candidate prediction is logged only.
        """
        X = features[self._feature_columns]

        prod_prob = float(self._production.predict_proba(X)[:, 1][0])
        cand_prob = float(self._candidate.predict_proba(X)[:, 1][0])

        prod_score = _prob_to_score(prod_prob)
        cand_score = _prob_to_score(cand_prob)

        comparison = ShadowPrediction(
            production_probability=prod_prob,
            candidate_probability=cand_prob,
            production_score=prod_score,
            candidate_score=cand_score,
            delta_probability=cand_prob - prod_prob,
            delta_score=cand_score - prod_score,
        )

        with self._lock:
            self._comparisons.append(comparison)

        return comparison

    def get_summary(self) -> ShadowComparisonSummary:
        """Compute summary statistics from all recorded comparisons.

        Returns:
            ShadowComparisonSummary with distribution comparison metrics.
        """
        with self._lock:
            if not self._comparisons:
                return ShadowComparisonSummary()

            prod_probs = np.array([c.production_probability for c in self._comparisons])
            cand_probs = np.array([c.candidate_probability for c in self._comparisons])
            deltas = np.array([c.delta_probability for c in self._comparisons])
            score_deltas = np.array([c.delta_score for c in self._comparisons])

        correlation = 0.0
        if len(prod_probs) > 1 and np.std(prod_probs) > 0 and np.std(cand_probs) > 0:
            correlation = float(np.corrcoef(prod_probs, cand_probs)[0, 1])

        return ShadowComparisonSummary(
            n_predictions=len(prod_probs),
            mean_probability_delta=float(np.mean(deltas)),
            std_probability_delta=float(np.std(deltas)),
            mean_score_delta=float(np.mean(score_deltas)),
            correlation=correlation,
            production_mean_prob=float(np.mean(prod_probs)),
            candidate_mean_prob=float(np.mean(cand_probs)),
            max_absolute_delta=float(np.max(np.abs(deltas))),
        )

    def stop(self) -> ShadowComparisonSummary:
        """Stop shadow mode and return final comparison summary.

        Returns:
            Final ShadowComparisonSummary.
        """
        self._active = False
        summary = self.get_summary()
        logger.info(
            "Shadow deployment stopped after %d predictions. "
            "Mean delta: %.4f, correlation: %.4f.",
            summary.n_predictions,
            summary.mean_probability_delta,
            summary.correlation,
        )
        return summary


def _prob_to_score(probability: float) -> int:
    """Convert probability to VyceScore (300-900 range).

    Lower probability of default = higher credit score.
    """
    score = 300 + int((1.0 - probability) * 600)
    return max(300, min(900, score))
