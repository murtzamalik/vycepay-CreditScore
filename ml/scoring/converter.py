"""Score conversion for VyceScore credit scoring.

Converts raw probability of default (0-1) to VyceScore (300-900) and
provides score interpretation labels per BRD Section 4.3.

Formula: vyceScore = 300 + (1 - probability) * 600

LOW probability of default = HIGH VyceScore = good credit.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np
from numpy.typing import ArrayLike

logger = logging.getLogger(__name__)

SCORE_MIN = 300
SCORE_MAX = 900
SCORE_RANGE = SCORE_MAX - SCORE_MIN  # 600


class RiskCategory(str, Enum):
    """Score interpretation labels per BRD Section 4.3."""

    VERY_LOW_RISK = "Very Low Risk"
    LOW_RISK = "Low Risk"
    MEDIUM_RISK = "Medium Risk"
    HIGH_RISK = "High Risk"
    VERY_HIGH_RISK = "Very High Risk"


# Score band definitions: (lower_bound_inclusive, upper_bound_inclusive, category)
SCORE_BANDS: list[tuple[int, int, RiskCategory]] = [
    (800, 900, RiskCategory.VERY_LOW_RISK),
    (700, 799, RiskCategory.LOW_RISK),
    (600, 699, RiskCategory.MEDIUM_RISK),
    (500, 599, RiskCategory.HIGH_RISK),
    (300, 499, RiskCategory.VERY_HIGH_RISK),
]


@dataclass(frozen=True)
class ScoreResult:
    """Complete score conversion result.

    Attributes:
        score: VyceScore (300-900), integer.
        probability: Original probability of default (0-1).
        risk_category: Human-readable risk label.
        confidence_interval: Optional (lower, upper) confidence bounds.
    """

    score: int
    probability: float
    risk_category: str
    confidence_interval: tuple[int, int] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to a JSON-serializable dict."""
        result: dict[str, Any] = {
            "score": self.score,
            "probability": round(self.probability, 6),
            "risk_category": self.risk_category,
        }
        if self.confidence_interval is not None:
            result["confidence_interval"] = {
                "lower": self.confidence_interval[0],
                "upper": self.confidence_interval[1],
            }
        return result


def probability_to_score(probability: float) -> int:
    """Convert probability of default to VyceScore.

    Formula: score = 300 + (1 - probability) * 600

    A probability of 0.0 yields 900 (lowest risk).
    A probability of 1.0 yields 300 (highest risk).

    Args:
        probability: Probability of default, in [0, 1].

    Returns:
        VyceScore integer in [300, 900].

    Raises:
        ValueError: If probability is not in [0, 1].
    """
    if not (0.0 <= probability <= 1.0):
        if math.isnan(probability):
            logger.warning("NaN probability received, returning minimum score")
            return SCORE_MIN
        raise ValueError(
            f"Probability must be in [0, 1], got {probability}"
        )

    raw_score = SCORE_MIN + (1.0 - probability) * SCORE_RANGE
    return int(np.clip(round(raw_score), SCORE_MIN, SCORE_MAX))


def score_to_probability(score: int) -> float:
    """Convert VyceScore back to probability of default.

    Inverse of probability_to_score:
        probability = 1 - (score - 300) / 600

    Args:
        score: VyceScore in [300, 900].

    Returns:
        Probability of default in [0, 1].

    Raises:
        ValueError: If score is not in [300, 900].
    """
    if not (SCORE_MIN <= score <= SCORE_MAX):
        raise ValueError(
            f"Score must be in [{SCORE_MIN}, {SCORE_MAX}], got {score}"
        )
    return 1.0 - (score - SCORE_MIN) / SCORE_RANGE


def get_risk_category(score: int) -> str:
    """Get the risk category label for a VyceScore.

    Score bands per BRD Section 4.3:
        800-900: Very Low Risk
        700-799: Low Risk
        600-699: Medium Risk
        500-599: High Risk
        300-499: Very High Risk

    Args:
        score: VyceScore in [300, 900].

    Returns:
        Risk category label string.

    Raises:
        ValueError: If score is outside valid range.
    """
    if not (SCORE_MIN <= score <= SCORE_MAX):
        raise ValueError(
            f"Score must be in [{SCORE_MIN}, {SCORE_MAX}], got {score}"
        )

    for lower, upper, category in SCORE_BANDS:
        if lower <= score <= upper:
            return category.value

    # Should never reach here if SCORE_BANDS covers full range
    return RiskCategory.VERY_HIGH_RISK.value


def compute_confidence_interval(
    probability: float,
    *,
    n_samples: int = 100,
    confidence_level: float = 0.95,
    model_uncertainty: float = 0.05,
) -> tuple[int, int]:
    """Compute a confidence interval for the VyceScore.

    Uses a simple normal approximation around the predicted probability
    to estimate score uncertainty.  The interval width depends on:
    - Model uncertainty (epistemic): how confident the model is.
    - Sample size: more data = narrower interval.
    - Base probability: extreme probabilities have tighter intervals.

    Args:
        probability: Predicted probability of default.
        n_samples: Number of training samples seen for this entity's
            segment. More samples = narrower interval.
        confidence_level: Confidence level (e.g., 0.95 for 95% CI).
        model_uncertainty: Base model uncertainty factor. Higher values
            produce wider intervals.

    Returns:
        Tuple of (lower_score, upper_score) as integers.
    """
    from scipy import stats

    # Z-score for confidence level
    z = stats.norm.ppf(1 - (1 - confidence_level) / 2)

    # Standard error of the probability estimate
    # Combines binomial variance with model uncertainty
    binomial_se = math.sqrt(probability * (1 - probability) / max(n_samples, 1))
    total_se = math.sqrt(binomial_se**2 + model_uncertainty**2)

    prob_lower = max(0.0, probability - z * total_se)
    prob_upper = min(1.0, probability + z * total_se)

    # Convert to scores (note: higher probability = lower score)
    score_upper = probability_to_score(prob_lower)
    score_lower = probability_to_score(prob_upper)

    return (score_lower, score_upper)


def convert_score(
    probability: float,
    *,
    include_confidence: bool = False,
    n_samples: int = 100,
    confidence_level: float = 0.95,
    model_uncertainty: float = 0.05,
) -> ScoreResult:
    """Full score conversion: probability to score + category + confidence.

    This is the primary entry point for score conversion.

    Args:
        probability: Probability of default in [0, 1].
        include_confidence: Whether to compute confidence interval.
        n_samples: Number of training samples for CI calculation.
        confidence_level: Confidence level for CI calculation.
        model_uncertainty: Model uncertainty for CI calculation.

    Returns:
        ScoreResult with score, category, and optional confidence interval.
    """
    score = probability_to_score(probability)
    category = get_risk_category(score)

    ci: tuple[int, int] | None = None
    if include_confidence:
        ci = compute_confidence_interval(
            probability,
            n_samples=n_samples,
            confidence_level=confidence_level,
            model_uncertainty=model_uncertainty,
        )

    return ScoreResult(
        score=score,
        probability=probability,
        risk_category=category,
        confidence_interval=ci,
    )


def convert_batch(
    probabilities: ArrayLike,
    *,
    include_confidence: bool = False,
) -> list[ScoreResult]:
    """Convert a batch of probabilities to ScoreResults.

    Args:
        probabilities: Array of probabilities of default.
        include_confidence: Whether to compute confidence intervals.

    Returns:
        List of ScoreResult objects.
    """
    probs = np.asarray(probabilities, dtype=float)
    return [
        convert_score(float(p), include_confidence=include_confidence)
        for p in probs
    ]
