"""Tests for deployment gates in ml.training.evaluation (Phase 10.4)."""

from __future__ import annotations

import pytest

from ml.training.evaluation import (
    DEPLOYMENT_GATES,
    DeploymentGate,
    GateCheckResult,
    check_deployment_gates,
)


class TestDeploymentGate:
    """Tests for the DeploymentGate dataclass."""

    def test_higher_is_better_passes(self) -> None:
        gate = DeploymentGate("auc_roc", 0.75, "higher_is_better")
        assert gate.check(0.80) is True

    def test_higher_is_better_fails(self) -> None:
        gate = DeploymentGate("auc_roc", 0.75, "higher_is_better")
        assert gate.check(0.70) is False

    def test_lower_is_better_passes(self) -> None:
        gate = DeploymentGate("calibration_error", 0.05, "lower_is_better")
        assert gate.check(0.03) is True

    def test_lower_is_better_fails(self) -> None:
        gate = DeploymentGate("calibration_error", 0.05, "lower_is_better")
        assert gate.check(0.06) is False

    def test_exactly_at_threshold_higher_fails(self) -> None:
        gate = DeploymentGate("auc_roc", 0.75, "higher_is_better")
        assert gate.check(0.75) is False

    def test_exactly_at_threshold_lower_fails(self) -> None:
        gate = DeploymentGate("calibration_error", 0.05, "lower_is_better")
        assert gate.check(0.05) is False


class TestCheckDeploymentGates:
    """Tests for check_deployment_gates."""

    def test_all_gates_pass(self) -> None:
        metrics = {
            "auc_roc": 0.80,
            "precision_at_1000": 0.35,
            "calibration_error": 0.03,
        }
        all_passed, results = check_deployment_gates(metrics)

        assert all_passed is True
        assert len(results) == len(DEPLOYMENT_GATES)
        assert all(r.passed for r in results)

    def test_some_gates_fail(self) -> None:
        metrics = {
            "auc_roc": 0.70,  # Below 0.75
            "precision_at_1000": 0.35,
            "calibration_error": 0.03,
        }
        all_passed, results = check_deployment_gates(metrics)

        assert all_passed is False
        failed = [r for r in results if not r.passed]
        assert len(failed) == 1
        assert failed[0].gate.metric_name == "auc_roc"

    def test_all_gates_fail(self) -> None:
        metrics = {
            "auc_roc": 0.60,
            "precision_at_1000": 0.10,
            "calibration_error": 0.10,
        }
        all_passed, results = check_deployment_gates(metrics)

        assert all_passed is False
        failed = [r for r in results if not r.passed]
        assert len(failed) == 3

    def test_missing_metric_fails_gate(self) -> None:
        metrics = {
            "auc_roc": 0.80,
            # precision_at_1000 missing
            "calibration_error": 0.03,
        }
        all_passed, results = check_deployment_gates(metrics)
        assert all_passed is False

    def test_custom_gates(self) -> None:
        gates = [
            DeploymentGate("auc_roc", 0.90, "higher_is_better"),
        ]
        metrics = {"auc_roc": 0.85}
        all_passed, results = check_deployment_gates(metrics, gates)

        assert all_passed is False
        assert len(results) == 1

    def test_default_gates_match_brd(self) -> None:
        """BRD specifies: AUC > 0.75, Precision@1000 > 0.30, ECE < 0.05."""
        gate_names = {g.metric_name for g in DEPLOYMENT_GATES}
        assert "auc_roc" in gate_names
        assert "precision_at_1000" in gate_names
        assert "calibration_error" in gate_names
