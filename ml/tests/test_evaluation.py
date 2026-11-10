"""Tests for ml.training.evaluation — model evaluation and reporting."""

from __future__ import annotations

import numpy as np
import pytest

from ml.training.evaluation import (
    PERFORMANCE_TARGETS,
    PerformanceTarget,
    check_performance_targets,
    compute_fairness_metrics,
    evaluate_model,
    generate_evaluation_report,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def perfect_predictions() -> tuple[np.ndarray, np.ndarray]:
    """Labels and probabilities for a near-perfect classifier.

    Positive class gets probabilities in [0.9, 1.0] and negative in [0.0, 0.05]
    so that precision@K, AUC, and calibration all pass BRD targets.
    """
    np.random.seed(42)
    n_pos = 500
    n_neg = 1500
    y_true = np.concatenate([np.ones(n_pos), np.zeros(n_neg)])
    y_prob = np.where(
        y_true == 1,
        np.random.uniform(0.90, 0.99, n_pos + n_neg),
        np.random.uniform(0.01, 0.05, n_pos + n_neg),
    )
    return y_true, y_prob


@pytest.fixture()
def mediocre_predictions() -> tuple[np.ndarray, np.ndarray]:
    """Labels and probabilities for a mediocre classifier."""
    np.random.seed(42)
    n = 2000
    y_true = np.concatenate([np.ones(400), np.zeros(1600)])
    y_prob = np.where(
        y_true == 1,
        np.random.uniform(0.3, 0.9, n),
        np.random.uniform(0.1, 0.7, n),
    )
    return y_true, y_prob


@pytest.fixture()
def random_predictions() -> tuple[np.ndarray, np.ndarray]:
    """Labels and probabilities for a random classifier."""
    np.random.seed(42)
    n = 1000
    y_true = np.concatenate([np.ones(200), np.zeros(800)])
    y_prob = np.random.uniform(0.0, 1.0, n)
    return y_true, y_prob


# ---------------------------------------------------------------------------
# Test PerformanceTarget
# ---------------------------------------------------------------------------

class TestPerformanceTarget:
    def test_higher_is_better_pass(self) -> None:
        target = PerformanceTarget("auc_roc", 0.75, "higher_is_better")
        assert target.check(0.80) is True

    def test_higher_is_better_fail(self) -> None:
        target = PerformanceTarget("auc_roc", 0.75, "higher_is_better")
        assert target.check(0.70) is False

    def test_lower_is_better_pass(self) -> None:
        target = PerformanceTarget("calibration_error", 0.05, "lower_is_better")
        assert target.check(0.03) is True

    def test_lower_is_better_fail(self) -> None:
        target = PerformanceTarget("calibration_error", 0.05, "lower_is_better")
        assert target.check(0.10) is False


# ---------------------------------------------------------------------------
# Test evaluate_model
# ---------------------------------------------------------------------------

class TestEvaluateModel:
    def test_returns_all_metrics(
        self, perfect_predictions: tuple[np.ndarray, np.ndarray]
    ) -> None:
        y_true, y_prob = perfect_predictions
        metrics = evaluate_model(y_true, y_prob)
        assert "auc_roc" in metrics
        assert "ks_statistic" in metrics
        assert "calibration_error" in metrics
        assert "precision_at_1000" in metrics

    def test_perfect_classifier_high_auc(
        self, perfect_predictions: tuple[np.ndarray, np.ndarray]
    ) -> None:
        y_true, y_prob = perfect_predictions
        metrics = evaluate_model(y_true, y_prob)
        assert metrics["auc_roc"] > 0.95

    def test_random_classifier_auc_near_half(
        self, random_predictions: tuple[np.ndarray, np.ndarray]
    ) -> None:
        y_true, y_prob = random_predictions
        metrics = evaluate_model(y_true, y_prob)
        assert 0.3 < metrics["auc_roc"] < 0.7

    def test_custom_k_values(
        self, perfect_predictions: tuple[np.ndarray, np.ndarray]
    ) -> None:
        y_true, y_prob = perfect_predictions
        metrics = evaluate_model(
            y_true, y_prob, precision_k_values=[50, 200]
        )
        assert "precision_at_50" in metrics
        assert "precision_at_200" in metrics
        assert "precision_at_1000" not in metrics

    def test_metric_ranges(
        self, mediocre_predictions: tuple[np.ndarray, np.ndarray]
    ) -> None:
        y_true, y_prob = mediocre_predictions
        metrics = evaluate_model(y_true, y_prob)
        assert 0.0 <= metrics["auc_roc"] <= 1.0
        assert 0.0 <= metrics["ks_statistic"] <= 1.0
        assert metrics["calibration_error"] >= 0.0


# ---------------------------------------------------------------------------
# Test check_performance_targets
# ---------------------------------------------------------------------------

class TestCheckPerformanceTargets:
    def test_all_pass(
        self, perfect_predictions: tuple[np.ndarray, np.ndarray]
    ) -> None:
        y_true, y_prob = perfect_predictions
        metrics = evaluate_model(y_true, y_prob)
        results = check_performance_targets(metrics)
        for name, check in results.items():
            assert check["passed"] is True, f"{name} should pass"

    def test_missing_metric(self) -> None:
        metrics = {"auc_roc": 0.80}  # Missing other metrics
        results = check_performance_targets(metrics)
        assert "auc_roc" in results
        assert results["auc_roc"]["passed"] is True

    def test_custom_targets(self) -> None:
        metrics = {"custom_metric": 0.90}
        targets = [
            PerformanceTarget("custom_metric", 0.85, "higher_is_better")
        ]
        results = check_performance_targets(metrics, targets)
        assert results["custom_metric"]["passed"] is True

    def test_result_structure(self) -> None:
        metrics = {"auc_roc": 0.80}
        results = check_performance_targets(metrics)
        assert "target" in results["auc_roc"]
        assert "actual" in results["auc_roc"]
        assert "passed" in results["auc_roc"]
        assert "direction" in results["auc_roc"]


# ---------------------------------------------------------------------------
# Test compute_fairness_metrics
# ---------------------------------------------------------------------------

class TestComputeFairnessMetrics:
    def test_two_groups(self) -> None:
        np.random.seed(42)
        n = 200
        y_true = np.concatenate([np.ones(40), np.zeros(160)])
        y_prob = np.random.uniform(0.0, 1.0, n)
        groups = np.concatenate([
            np.full(100, "urban"),
            np.full(100, "rural"),
        ])
        result = compute_fairness_metrics(y_true, y_prob, groups)
        assert "group_metrics" in result
        assert "urban" in result["group_metrics"]
        assert "rural" in result["group_metrics"]
        assert "demographic_parity_difference" in result
        assert result["n_groups"] == 2

    def test_single_group(self) -> None:
        y_true = np.array([0, 0, 1, 1])
        y_prob = np.array([0.1, 0.2, 0.8, 0.9])
        groups = np.array(["a", "a", "a", "a"])
        result = compute_fairness_metrics(y_true, y_prob, groups)
        assert result["demographic_parity_difference"] == 0.0

    def test_threshold_effect(self) -> None:
        y_true = np.array([0, 0, 1, 1, 0, 1])
        y_prob = np.array([0.3, 0.4, 0.7, 0.8, 0.2, 0.6])
        groups = np.array(["a", "a", "a", "b", "b", "b"])

        result_low = compute_fairness_metrics(
            y_true, y_prob, groups, threshold=0.3
        )
        result_high = compute_fairness_metrics(
            y_true, y_prob, groups, threshold=0.9
        )
        # Different thresholds should produce different positive rates
        assert result_low["threshold"] == 0.3
        assert result_high["threshold"] == 0.9


# ---------------------------------------------------------------------------
# Test generate_evaluation_report
# ---------------------------------------------------------------------------

class TestGenerateEvaluationReport:
    def test_report_structure(
        self, perfect_predictions: tuple[np.ndarray, np.ndarray]
    ) -> None:
        y_true, y_prob = perfect_predictions
        report = generate_evaluation_report(y_true, y_prob)
        assert "metadata" in report
        assert "metrics" in report
        assert "performance_targets" in report
        assert "all_targets_passed" in report
        assert "probability_distribution" in report

    def test_metadata_fields(
        self, perfect_predictions: tuple[np.ndarray, np.ndarray]
    ) -> None:
        y_true, y_prob = perfect_predictions
        report = generate_evaluation_report(
            y_true, y_prob,
            model_name="test-model",
            model_version="v1",
            dataset_name="holdout",
        )
        meta = report["metadata"]
        assert meta["model_name"] == "test-model"
        assert meta["model_version"] == "v1"
        assert meta["dataset"] == "holdout"
        assert meta["n_samples"] == len(y_true)
        assert 0.0 <= meta["positive_rate"] <= 1.0

    def test_with_fairness(
        self, perfect_predictions: tuple[np.ndarray, np.ndarray]
    ) -> None:
        y_true, y_prob = perfect_predictions
        groups = np.random.choice(["A", "B"], size=len(y_true))
        report = generate_evaluation_report(
            y_true, y_prob, sensitive_attribute=groups
        )
        assert "fairness" in report

    def test_without_fairness(
        self, perfect_predictions: tuple[np.ndarray, np.ndarray]
    ) -> None:
        y_true, y_prob = perfect_predictions
        report = generate_evaluation_report(y_true, y_prob)
        assert "fairness" not in report

    def test_probability_distribution(
        self, perfect_predictions: tuple[np.ndarray, np.ndarray]
    ) -> None:
        y_true, y_prob = perfect_predictions
        report = generate_evaluation_report(y_true, y_prob)
        dist = report["probability_distribution"]
        assert "mean" in dist
        assert "std" in dist
        assert "min" in dist
        assert "max" in dist
        assert "median" in dist
