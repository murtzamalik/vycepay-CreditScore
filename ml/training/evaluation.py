"""Model evaluation for VyceScore training pipeline.

Computes AUC-ROC, Precision@K, Expected Calibration Error, KS statistic,
and fairness metrics.  Generates a structured evaluation report for model
acceptance decisions.

Performance targets (from BRD):
    - AUC-ROC > 0.75
    - Precision@1000 > 0.30
    - Expected Calibration Error < 0.05
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
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

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PerformanceTarget:
    """A single performance target with pass/fail logic."""

    metric_name: str
    threshold: float
    direction: str  # "higher_is_better" or "lower_is_better"

    def check(self, actual: float) -> bool:
        """Return True if the actual value meets the target."""
        if self.direction == "lower_is_better":
            return actual < self.threshold
        return actual > self.threshold


# BRD performance targets.
PERFORMANCE_TARGETS: list[PerformanceTarget] = [
    PerformanceTarget("auc_roc", 0.75, "higher_is_better"),
    PerformanceTarget("precision_at_1000", 0.30, "higher_is_better"),
    PerformanceTarget("calibration_error", 0.05, "lower_is_better"),
]


def evaluate_model(
    y_true: ArrayLike,
    y_prob: ArrayLike,
    *,
    precision_k_values: list[int] | None = None,
) -> dict[str, float]:
    """Compute all evaluation metrics.

    Args:
        y_true: Binary ground truth labels (0 or 1).
        y_prob: Predicted probabilities for the positive class.
        precision_k_values: List of K values for Precision@K.
            Defaults to [100, 500, 1000].

    Returns:
        Dict of metric name to value.
    """
    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob)

    k_values = precision_k_values or [100, 500, 1000]

    metrics: dict[str, float] = {
        "auc_roc": auc_roc(y_true, y_prob),
        "ks_statistic": ks_statistic(y_true, y_prob),
        "calibration_error": calibration_error(y_true, y_prob),
    }

    for k in k_values:
        metrics[f"precision_at_{k}"] = precision_at_k(y_true, y_prob, k=k)

    return metrics


def check_performance_targets(
    metrics: dict[str, float],
    targets: list[PerformanceTarget] | None = None,
) -> dict[str, dict[str, Any]]:
    """Check metrics against performance targets.

    Args:
        metrics: Dict of metric name to value.
        targets: Performance targets to check. Uses BRD defaults if None.

    Returns:
        Dict mapping metric name to check result with keys:
        target, actual, passed, direction.
    """
    if targets is None:
        targets = PERFORMANCE_TARGETS

    results: dict[str, dict[str, Any]] = {}

    for target in targets:
        actual = metrics.get(target.metric_name)
        if actual is None:
            logger.warning(
                "Metric '%s' not found in results, skipping target check.",
                target.metric_name,
            )
            continue

        passed = target.check(actual)
        op = "<" if target.direction == "lower_is_better" else ">"

        results[target.metric_name] = {
            "target": f"{op} {target.threshold}",
            "actual": round(actual, 6),
            "passed": passed,
            "direction": target.direction,
        }

        if not passed:
            logger.warning(
                "BELOW TARGET: %s = %.4f (target %s %.4f)",
                target.metric_name,
                actual,
                op,
                target.threshold,
            )

    return results


def compute_fairness_metrics(
    y_true: ArrayLike,
    y_prob: ArrayLike,
    sensitive_attribute: ArrayLike,
    *,
    threshold: float = 0.5,
) -> dict[str, Any]:
    """Compute fairness metrics (demographic parity check).

    This is a placeholder implementation that computes basic demographic
    parity metrics.  Full fairness analysis should include equalized odds,
    calibration across groups, and disparate impact ratio.

    Args:
        y_true: Binary ground truth labels.
        y_prob: Predicted probabilities.
        sensitive_attribute: Group membership array (e.g., region, gender).
        threshold: Classification threshold for positive predictions.

    Returns:
        Dict with fairness metrics per group and overall disparity.
    """
    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob)
    groups = np.asarray(sensitive_attribute)

    y_pred = (y_prob >= threshold).astype(int)

    unique_groups = np.unique(groups)
    group_metrics: dict[str, dict[str, float]] = {}

    for group in unique_groups:
        mask = groups == group
        n_group = int(np.sum(mask))
        if n_group == 0:
            continue

        positive_rate = float(np.mean(y_pred[mask]))
        true_positive_rate = float(
            np.mean(y_true[mask][y_pred[mask] == 1])
        ) if np.sum(y_pred[mask]) > 0 else 0.0

        group_metrics[str(group)] = {
            "n_samples": n_group,
            "positive_prediction_rate": round(positive_rate, 4),
            "true_positive_rate": round(true_positive_rate, 4),
            "mean_probability": round(float(np.mean(y_prob[mask])), 4),
        }

    # Demographic parity: max difference in positive prediction rates
    rates = [g["positive_prediction_rate"] for g in group_metrics.values()]
    demographic_parity_diff = max(rates) - min(rates) if len(rates) > 1 else 0.0

    return {
        "group_metrics": group_metrics,
        "demographic_parity_difference": round(demographic_parity_diff, 4),
        "n_groups": len(unique_groups),
        "threshold": threshold,
    }


def generate_evaluation_report(
    y_true: ArrayLike,
    y_prob: ArrayLike,
    *,
    model_name: str = "vycescore-xgboost",
    model_version: str | None = None,
    dataset_name: str = "test",
    precision_k_values: list[int] | None = None,
    sensitive_attribute: ArrayLike | None = None,
) -> dict[str, Any]:
    """Generate a comprehensive evaluation report.

    Args:
        y_true: Binary ground truth labels.
        y_prob: Predicted probabilities for the positive class.
        model_name: Name of the model being evaluated.
        model_version: Optional version identifier.
        dataset_name: Name of the evaluation dataset.
        precision_k_values: K values for Precision@K.
        sensitive_attribute: Optional group membership for fairness analysis.

    Returns:
        Structured evaluation report as a dict.
    """
    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob)

    # Compute metrics
    metrics = evaluate_model(
        y_true, y_prob, precision_k_values=precision_k_values
    )

    # Check performance targets
    target_checks = check_performance_targets(metrics)
    all_passed = all(c["passed"] for c in target_checks.values())

    report: dict[str, Any] = {
        "metadata": {
            "model_name": model_name,
            "model_version": model_version,
            "dataset": dataset_name,
            "n_samples": int(len(y_true)),
            "positive_rate": round(float(np.mean(y_true)), 4),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "metrics": {k: round(v, 6) for k, v in metrics.items()},
        "performance_targets": target_checks,
        "all_targets_passed": all_passed,
    }

    # Fairness metrics if sensitive attribute provided
    if sensitive_attribute is not None:
        report["fairness"] = compute_fairness_metrics(
            y_true, y_prob, sensitive_attribute
        )

    # Score distribution summary
    report["probability_distribution"] = {
        "mean": round(float(np.mean(y_prob)), 4),
        "std": round(float(np.std(y_prob)), 4),
        "min": round(float(np.min(y_prob)), 4),
        "max": round(float(np.max(y_prob)), 4),
        "median": round(float(np.median(y_prob)), 4),
    }

    if all_passed:
        logger.info(
            "All performance targets PASSED for %s", model_name
        )
    else:
        failed = [k for k, v in target_checks.items() if not v["passed"]]
        logger.warning(
            "Performance targets FAILED for %s: %s", model_name, failed
        )

    return report


# ---------------------------------------------------------------------------
# Deployment gate — Phase 10.4
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DeploymentGate:
    """A single deployment gate with metric name, threshold, and direction.

    All gates must pass before a model can be deployed to production.
    """

    metric_name: str
    threshold: float
    direction: str  # "higher_is_better" or "lower_is_better"
    description: str = ""

    def check(self, actual: float) -> bool:
        """Return True if the actual value passes the gate."""
        if self.direction == "lower_is_better":
            return actual < self.threshold
        return actual > self.threshold


# BRD-mandated deployment gates (stricter than monitoring targets).
DEPLOYMENT_GATES: list[DeploymentGate] = [
    DeploymentGate(
        "auc_roc",
        0.75,
        "higher_is_better",
        "AUC-ROC must exceed 0.75 for deployment",
    ),
    DeploymentGate(
        "precision_at_1000",
        0.30,
        "higher_is_better",
        "Precision@1000 must exceed 0.30 for deployment",
    ),
    DeploymentGate(
        "calibration_error",
        0.05,
        "lower_is_better",
        "Expected Calibration Error must be below 0.05",
    ),
]


@dataclass
class GateCheckResult:
    """Result of a deployment gate check.

    Attributes:
        gate: The gate that was checked.
        actual: The actual metric value.
        passed: Whether the gate passed.
    """

    gate: DeploymentGate
    actual: float
    passed: bool


def check_deployment_gates(
    metrics: dict[str, float],
    gates: list[DeploymentGate] | None = None,
) -> tuple[bool, list[GateCheckResult]]:
    """Check metrics against all deployment gates.

    All gates must pass for a model to be eligible for deployment.

    Args:
        metrics: Dict of metric name to value.
        gates: Deployment gates to check. Uses BRD defaults if None.

    Returns:
        Tuple of (all_passed, list of gate check results).
    """
    if gates is None:
        gates = DEPLOYMENT_GATES

    results: list[GateCheckResult] = []
    all_passed = True

    for gate in gates:
        actual = metrics.get(gate.metric_name)
        if actual is None:
            logger.warning(
                "Gate metric '%s' not found in results; gate FAILS.",
                gate.metric_name,
            )
            results.append(
                GateCheckResult(gate=gate, actual=0.0, passed=False)
            )
            all_passed = False
            continue

        passed = gate.check(actual)
        results.append(
            GateCheckResult(gate=gate, actual=actual, passed=passed)
        )

        if not passed:
            all_passed = False
            op = "<" if gate.direction == "lower_is_better" else ">"
            logger.warning(
                "DEPLOYMENT GATE FAILED: %s = %.4f (required %s %.4f). %s",
                gate.metric_name,
                actual,
                op,
                gate.threshold,
                gate.description,
            )

    if all_passed:
        logger.info("All %d deployment gates PASSED.", len(gates))
    else:
        n_failed = sum(1 for r in results if not r.passed)
        logger.warning(
            "%d of %d deployment gates FAILED.",
            n_failed,
            len(gates),
        )

    return all_passed, results
