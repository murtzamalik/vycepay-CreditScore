"""Feature and score drift detection using Population Stability Index (PSI).

PSI measures distribution shifts between a reference (training) dataset
and a production (scoring) dataset.  Standard metric in credit scoring
model monitoring to decide when retraining is needed.

PSI interpretation:
    < 0.10 -- No significant shift
    0.10 - 0.25 -- Moderate shift, investigate
    > 0.25 -- Significant shift, likely retraining required

This module also provides score distribution monitoring and aggregate
drift reports with alert thresholds.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike

logger = logging.getLogger(__name__)

PSI_THRESHOLD_OK = 0.10
PSI_THRESHOLD_WARNING = 0.25


@dataclass(frozen=True)
class DriftResult:
    """Result of a drift check for a single feature."""

    feature_name: str
    psi: float
    status: str  # "ok", "warning", "critical"


@dataclass(frozen=True)
class ScoreDistributionStats:
    """Score distribution summary for comparison.

    Attributes:
        mean: Mean score value.
        std: Standard deviation.
        median: Median score value.
        p5: 5th percentile.
        p95: 95th percentile.
        n_samples: Number of samples.
    """

    mean: float
    std: float
    median: float
    p5: float
    p95: float
    n_samples: int


@dataclass
class DriftReport:
    """Comprehensive drift monitoring report.

    Attributes:
        feature_results: Per-feature drift results.
        score_drift: PSI of the score distribution (None if not computed).
        score_reference_stats: Reference score distribution stats.
        score_production_stats: Production score distribution stats.
        overall_status: Aggregate status (ok / warning / critical).
        requires_retraining: Whether drift severity warrants retraining.
        alert_message: Human-readable alert text (None if no alert).
        checked_at: UTC timestamp of the drift check.
    """

    feature_results: list[DriftResult]
    score_drift: float | None = None
    score_reference_stats: ScoreDistributionStats | None = None
    score_production_stats: ScoreDistributionStats | None = None
    overall_status: str = "ok"
    requires_retraining: bool = False
    alert_message: str | None = None
    checked_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


def calculate_psi(
    reference: ArrayLike,
    production: ArrayLike,
    n_bins: int = 10,
    *,
    eps: float = 1e-6,
) -> float:
    """Calculate the Population Stability Index (PSI) between two distributions.

    PSI = SUM( (p_i - q_i) * ln(p_i / q_i) )

    where p_i is the proportion in bin i for the production distribution
    and q_i is the proportion for the reference distribution.

    Args:
        reference: Array of values from the reference (training) dataset.
        production: Array of values from the production (scoring) dataset.
        n_bins: Number of equal-width bins derived from the reference
            distribution's range.
        eps: Small constant to avoid division by zero and log(0).

    Returns:
        PSI value >= 0. Lower is better (less drift).
    """
    reference = np.asarray(reference, dtype=float)
    production = np.asarray(production, dtype=float)

    # Create bins from the reference distribution
    bin_edges = np.linspace(
        np.min(reference), np.max(reference), n_bins + 1
    )
    # Extend edges slightly to capture all production values
    bin_edges[0] = min(bin_edges[0], np.min(production)) - eps
    bin_edges[-1] = max(bin_edges[-1], np.max(production)) + eps

    ref_counts = np.histogram(reference, bins=bin_edges)[0].astype(float)
    prod_counts = np.histogram(production, bins=bin_edges)[0].astype(float)

    # Convert to proportions with smoothing
    ref_props = (ref_counts + eps) / (np.sum(ref_counts) + eps * n_bins)
    prod_props = (prod_counts + eps) / (np.sum(prod_counts) + eps * n_bins)

    # PSI formula
    psi = float(np.sum((prod_props - ref_props) * np.log(prod_props / ref_props)))
    return psi


def check_feature_drift(
    reference_df: pd.DataFrame,
    production_df: pd.DataFrame,
    feature_columns: list[str],
    *,
    n_bins: int = 10,
) -> list[DriftResult]:
    """Check drift across all features and return per-feature results.

    Args:
        reference_df: Reference (training) DataFrame.
        production_df: Production (scoring) DataFrame.
        feature_columns: List of feature column names to check.
        n_bins: Number of bins for PSI calculation.

    Returns:
        List of DriftResult, one per feature, sorted by PSI descending.
    """
    results: list[DriftResult] = []

    for col in feature_columns:
        psi = calculate_psi(
            reference_df[col].values,
            production_df[col].values,
            n_bins=n_bins,
        )

        if psi < PSI_THRESHOLD_OK:
            status = "ok"
        elif psi < PSI_THRESHOLD_WARNING:
            status = "warning"
            logger.warning("Moderate drift detected for %s: PSI=%.4f", col, psi)
        else:
            status = "critical"
            logger.error("Significant drift detected for %s: PSI=%.4f", col, psi)

        results.append(DriftResult(feature_name=col, psi=psi, status=status))

    results.sort(key=lambda r: r.psi, reverse=True)
    return results


def check_score_drift(
    reference_scores: ArrayLike,
    production_scores: ArrayLike,
    *,
    n_bins: int = 10,
) -> tuple[float, ScoreDistributionStats, ScoreDistributionStats]:
    """Check drift in the score distribution itself.

    Args:
        reference_scores: Reference (training period) scores.
        production_scores: Production (recent) scores.
        n_bins: Number of bins for PSI.

    Returns:
        Tuple of (score PSI, reference stats, production stats).
    """
    ref = np.asarray(reference_scores, dtype=float)
    prod = np.asarray(production_scores, dtype=float)

    psi = calculate_psi(ref, prod, n_bins=n_bins)

    ref_stats = _compute_distribution_stats(ref)
    prod_stats = _compute_distribution_stats(prod)

    if psi >= PSI_THRESHOLD_WARNING:
        logger.warning(
            "Score distribution drift detected: PSI=%.4f. "
            "Reference mean=%.1f, Production mean=%.1f.",
            psi,
            ref_stats.mean,
            prod_stats.mean,
        )
    elif psi >= PSI_THRESHOLD_OK:
        logger.info("Moderate score drift: PSI=%.4f.", psi)

    return psi, ref_stats, prod_stats


def generate_drift_report(
    reference_df: pd.DataFrame,
    production_df: pd.DataFrame,
    feature_columns: list[str],
    reference_scores: ArrayLike | None = None,
    production_scores: ArrayLike | None = None,
    *,
    n_bins: int = 10,
    critical_threshold: float = PSI_THRESHOLD_WARNING,
    warning_threshold: float = PSI_THRESHOLD_OK,
) -> DriftReport:
    """Generate a comprehensive drift monitoring report.

    Checks feature drift and optionally score drift, then determines
    overall status and whether retraining is recommended.

    Args:
        reference_df: Reference (training) feature DataFrame.
        production_df: Production (recent) feature DataFrame.
        feature_columns: Feature column names to monitor.
        reference_scores: Reference period scores (optional).
        production_scores: Production period scores (optional).
        n_bins: Bins for PSI.
        critical_threshold: PSI above this in any feature = critical.
        warning_threshold: PSI above this in any feature = warning.

    Returns:
        DriftReport with feature results, score drift, and overall status.
    """
    feature_results = check_feature_drift(
        reference_df, production_df, feature_columns, n_bins=n_bins
    )

    # Score drift
    score_psi: float | None = None
    ref_stats: ScoreDistributionStats | None = None
    prod_stats: ScoreDistributionStats | None = None

    if reference_scores is not None and production_scores is not None:
        score_psi, ref_stats, prod_stats = check_score_drift(
            reference_scores, production_scores, n_bins=n_bins
        )

    # Determine overall status
    max_feature_psi = max(r.psi for r in feature_results) if feature_results else 0.0
    max_psi = max(max_feature_psi, score_psi or 0.0)

    if max_psi >= critical_threshold:
        overall_status = "critical"
        requires_retraining = True
    elif max_psi >= warning_threshold:
        overall_status = "warning"
        requires_retraining = False
    else:
        overall_status = "ok"
        requires_retraining = False

    # Build alert message
    alert_message: str | None = None
    critical_features = [r for r in feature_results if r.status == "critical"]
    warning_features = [r for r in feature_results if r.status == "warning"]

    if critical_features or (score_psi is not None and score_psi >= critical_threshold):
        parts: list[str] = []
        if critical_features:
            names = [r.feature_name for r in critical_features]
            parts.append(
                f"Critical drift in features: {', '.join(names)}"
            )
        if score_psi is not None and score_psi >= critical_threshold:
            parts.append(f"Score distribution drift: PSI={score_psi:.4f}")
        alert_message = " | ".join(parts)
    elif warning_features:
        names = [r.feature_name for r in warning_features]
        alert_message = (
            f"Moderate drift in features: {', '.join(names)}. "
            f"Investigate before next retraining."
        )

    report = DriftReport(
        feature_results=feature_results,
        score_drift=score_psi,
        score_reference_stats=ref_stats,
        score_production_stats=prod_stats,
        overall_status=overall_status,
        requires_retraining=requires_retraining,
        alert_message=alert_message,
    )

    logger.info(
        "Drift report: status=%s, max_feature_PSI=%.4f, "
        "score_PSI=%s, retraining_recommended=%s.",
        overall_status,
        max_feature_psi,
        f"{score_psi:.4f}" if score_psi is not None else "N/A",
        requires_retraining,
    )

    return report


def _compute_distribution_stats(values: np.ndarray) -> ScoreDistributionStats:
    """Compute summary statistics for a distribution."""
    return ScoreDistributionStats(
        mean=float(np.mean(values)),
        std=float(np.std(values)),
        median=float(np.median(values)),
        p5=float(np.percentile(values, 5)),
        p95=float(np.percentile(values, 95)),
        n_samples=len(values),
    )
