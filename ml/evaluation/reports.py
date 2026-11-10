"""Generate comprehensive evaluation reports for VyceScore models.

Collects all metrics into a structured report dict suitable for
logging to MLflow, saving as JSON, or rendering in the Admin UI.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import numpy as np
from numpy.typing import ArrayLike

from ml.evaluation.metrics import (
    auc_roc,
    calibration_error,
    ks_statistic,
    precision_at_k,
)
from ml.models.xgboost.hyperparams import PERFORMANCE_TARGETS

logger = logging.getLogger(__name__)


def generate_evaluation_report(
    y_true: ArrayLike,
    y_prob: ArrayLike,
    *,
    model_name: str = "vycescore-xgboost",
    model_version: str | None = None,
    dataset_name: str = "test",
    precision_k_values: list[int] | None = None,
) -> dict[str, Any]:
    """Generate a full evaluation report with all credit scoring metrics.

    Args:
        y_true: Binary ground truth labels (0 or 1).
        y_prob: Predicted probabilities for the positive class.
        model_name: Name of the model being evaluated.
        model_version: Optional version identifier.
        dataset_name: Name of the evaluation dataset (e.g., 'test', 'holdout').
        precision_k_values: List of K values for Precision@K. Defaults
            to [100, 500, 1000].

    Returns:
        Dict containing all metrics, metadata, and pass/fail status
        against performance targets.
    """
    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob)

    k_values = precision_k_values or [100, 500, 1000]

    # Compute all metrics
    metrics: dict[str, float] = {
        "auc_roc": auc_roc(y_true, y_prob),
        "ks_statistic": ks_statistic(y_true, y_prob),
        "calibration_error": calibration_error(y_true, y_prob),
    }
    for k in k_values:
        metrics[f"precision_at_{k}"] = precision_at_k(y_true, y_prob, k=k)

    # Check against performance targets
    target_checks: dict[str, dict[str, Any]] = {}
    for metric_name, threshold in PERFORMANCE_TARGETS.items():
        actual = metrics.get(metric_name)
        if actual is None:
            continue
        if metric_name == "calibration_error":
            passed = actual < threshold
            target_checks[metric_name] = {
                "target": f"< {threshold}",
                "actual": round(actual, 4),
                "passed": passed,
            }
        else:
            passed = actual > threshold
            target_checks[metric_name] = {
                "target": f"> {threshold}",
                "actual": round(actual, 4),
                "passed": passed,
            }

    all_passed = all(check["passed"] for check in target_checks.values())

    report: dict[str, Any] = {
        "metadata": {
            "model_name": model_name,
            "model_version": model_version,
            "dataset": dataset_name,
            "n_samples": len(y_true),
            "positive_rate": float(np.mean(y_true)),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "metrics": {k: round(v, 6) for k, v in metrics.items()},
        "performance_targets": target_checks,
        "all_targets_passed": all_passed,
    }

    if all_passed:
        logger.info("All performance targets PASSED for %s", model_name)
    else:
        failed = [k for k, v in target_checks.items() if not v["passed"]]
        logger.warning(
            "Performance targets FAILED for %s: %s", model_name, failed
        )

    return report
