"""Evaluation metrics for credit scoring models.

Implements AUC-ROC, Precision@K, Expected Calibration Error (ECE), and
Kolmogorov-Smirnov statistic — the standard suite for validating
probability-of-default models.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike
from sklearn.metrics import roc_auc_score


def auc_roc(y_true: ArrayLike, y_prob: ArrayLike) -> float:
    """Compute Area Under the Receiver Operating Characteristic Curve.

    Args:
        y_true: Binary ground truth labels (0 or 1).
        y_prob: Predicted probabilities for the positive class.

    Returns:
        AUC-ROC score in [0, 1]. Target: > 0.75.
    """
    return float(roc_auc_score(y_true, y_prob))


def precision_at_k(
    y_true: ArrayLike,
    y_prob: ArrayLike,
    k: int = 1000,
) -> float:
    """Compute Precision@K — the fraction of true positives among the
    top K highest-risk predictions.

    This metric is critical for credit scoring: it answers "if we flag
    the top K riskiest applicants, what fraction are truly delinquent?"

    Args:
        y_true: Binary ground truth labels (0 or 1).
        y_prob: Predicted probabilities for the positive class.
        k: Number of top predictions to evaluate.

    Returns:
        Precision@K in [0, 1]. Target: > 0.30 at K=1000.
    """
    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob)

    # If k exceeds the number of samples, use all samples
    k = min(k, len(y_true))
    if k == 0:
        return 0.0

    # Get indices of top-k highest predicted probabilities
    top_k_indices = np.argsort(y_prob)[::-1][:k]
    precision = float(np.mean(y_true[top_k_indices]))
    return precision


def calibration_error(
    y_true: ArrayLike,
    y_prob: ArrayLike,
    n_bins: int = 10,
) -> float:
    """Compute Expected Calibration Error (ECE).

    Measures how well predicted probabilities match observed frequencies.
    A well-calibrated model has ECE close to 0.

    Args:
        y_true: Binary ground truth labels (0 or 1).
        y_prob: Predicted probabilities for the positive class.
        n_bins: Number of equal-width bins for calibration curve.

    Returns:
        ECE value >= 0. Target: < 0.05.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_prob = np.asarray(y_prob, dtype=float)

    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    total = len(y_true)

    for i in range(n_bins):
        mask = (y_prob > bin_edges[i]) & (y_prob <= bin_edges[i + 1])
        # Include lower bound for the first bin
        if i == 0:
            mask = (y_prob >= bin_edges[i]) & (y_prob <= bin_edges[i + 1])

        bin_count = np.sum(mask)
        if bin_count == 0:
            continue

        bin_true_freq = np.mean(y_true[mask])
        bin_pred_mean = np.mean(y_prob[mask])
        ece += (bin_count / total) * abs(bin_true_freq - bin_pred_mean)

    return float(ece)


def ks_statistic(y_true: ArrayLike, y_prob: ArrayLike) -> float:
    """Compute the Kolmogorov-Smirnov statistic.

    Measures the maximum separation between the cumulative distribution
    functions of positive and negative classes. Widely used in credit
    scoring to assess discriminatory power.

    Args:
        y_true: Binary ground truth labels (0 or 1).
        y_prob: Predicted probabilities for the positive class.

    Returns:
        KS statistic in [0, 1]. Higher = better separation.
    """
    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob)

    pos_probs = np.sort(y_prob[y_true == 1])
    neg_probs = np.sort(y_prob[y_true == 0])

    # Build CDFs
    all_thresholds = np.sort(np.unique(np.concatenate([pos_probs, neg_probs])))

    pos_cdf = np.searchsorted(pos_probs, all_thresholds, side="right") / len(pos_probs)
    neg_cdf = np.searchsorted(neg_probs, all_thresholds, side="right") / len(neg_probs)

    ks = float(np.max(np.abs(pos_cdf - neg_cdf)))
    return ks
