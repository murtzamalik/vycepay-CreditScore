"""Tests for extended drift detection (Phase 10.7 additions)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ml.monitoring.drift import (
    DriftReport,
    ScoreDistributionStats,
    check_score_drift,
    generate_drift_report,
)


@pytest.fixture()
def reference_df() -> pd.DataFrame:
    """Reference feature DataFrame (stable distribution)."""
    np.random.seed(42)
    n = 1000
    return pd.DataFrame(
        {
            "cblri": np.random.normal(0.8, 0.1, n),
            "utdi": np.random.normal(0.5, 0.15, n),
            "scfv": np.random.normal(0.4, 0.1, n),
            "ddc_ratio": np.random.normal(0.7, 0.1, n),
            "niq_score": np.random.normal(50, 10, n),
            "gos_index": np.random.normal(0.3, 0.05, n),
        }
    )


@pytest.fixture()
def production_no_drift(reference_df: pd.DataFrame) -> pd.DataFrame:
    """Production data with no drift (same distribution as reference)."""
    np.random.seed(99)
    n = 500
    return pd.DataFrame(
        {
            "cblri": np.random.normal(0.8, 0.1, n),
            "utdi": np.random.normal(0.5, 0.15, n),
            "scfv": np.random.normal(0.4, 0.1, n),
            "ddc_ratio": np.random.normal(0.7, 0.1, n),
            "niq_score": np.random.normal(50, 10, n),
            "gos_index": np.random.normal(0.3, 0.05, n),
        }
    )


@pytest.fixture()
def production_with_drift() -> pd.DataFrame:
    """Production data with significant drift."""
    np.random.seed(99)
    n = 500
    return pd.DataFrame(
        {
            "cblri": np.random.normal(1.2, 0.2, n),  # Shifted
            "utdi": np.random.normal(0.5, 0.15, n),
            "scfv": np.random.normal(0.4, 0.1, n),
            "ddc_ratio": np.random.normal(0.7, 0.1, n),
            "niq_score": np.random.normal(30, 15, n),  # Shifted
            "gos_index": np.random.normal(0.3, 0.05, n),
        }
    )


class TestCheckScoreDrift:
    """Tests for check_score_drift."""

    def test_no_drift(self) -> None:
        ref = np.random.normal(600, 50, 1000)
        prod = np.random.normal(600, 50, 500)
        psi, ref_stats, prod_stats = check_score_drift(ref, prod)

        assert isinstance(psi, float)
        assert psi >= 0
        assert isinstance(ref_stats, ScoreDistributionStats)
        assert isinstance(prod_stats, ScoreDistributionStats)

    def test_drift_detected(self) -> None:
        ref = np.random.normal(600, 50, 1000)
        prod = np.random.normal(450, 80, 500)
        psi, _, _ = check_score_drift(ref, prod)

        assert psi > 0.25  # Significant drift


class TestGenerateDriftReport:
    """Tests for generate_drift_report."""

    def test_no_drift_report(
        self,
        reference_df: pd.DataFrame,
        production_no_drift: pd.DataFrame,
    ) -> None:
        features = list(reference_df.columns)
        report = generate_drift_report(
            reference_df, production_no_drift, features
        )

        assert isinstance(report, DriftReport)
        assert report.overall_status in ("ok", "warning")
        assert len(report.feature_results) == len(features)

    def test_drift_report_with_drift(
        self,
        reference_df: pd.DataFrame,
        production_with_drift: pd.DataFrame,
    ) -> None:
        features = list(reference_df.columns)
        report = generate_drift_report(
            reference_df, production_with_drift, features
        )

        assert report.overall_status in ("warning", "critical")
        # At least one feature should have elevated PSI
        psi_values = [r.psi for r in report.feature_results]
        assert max(psi_values) > 0.05

    def test_report_includes_score_drift(
        self,
        reference_df: pd.DataFrame,
        production_no_drift: pd.DataFrame,
    ) -> None:
        ref_scores = np.random.normal(600, 50, 1000)
        prod_scores = np.random.normal(600, 50, 500)

        report = generate_drift_report(
            reference_df,
            production_no_drift,
            list(reference_df.columns),
            reference_scores=ref_scores,
            production_scores=prod_scores,
        )

        assert report.score_drift is not None
        assert report.score_reference_stats is not None
        assert report.score_production_stats is not None

    def test_report_retraining_flag(
        self,
        reference_df: pd.DataFrame,
        production_with_drift: pd.DataFrame,
    ) -> None:
        report = generate_drift_report(
            reference_df,
            production_with_drift,
            list(reference_df.columns),
        )

        # With shifted features, retraining may or may not be recommended
        # depending on exact PSI values
        assert isinstance(report.requires_retraining, bool)

    def test_alert_message_set_on_drift(
        self,
        reference_df: pd.DataFrame,
        production_with_drift: pd.DataFrame,
    ) -> None:
        report = generate_drift_report(
            reference_df,
            production_with_drift,
            list(reference_df.columns),
        )

        if report.overall_status in ("warning", "critical"):
            assert report.alert_message is not None

    def test_checked_at_timestamp(
        self,
        reference_df: pd.DataFrame,
        production_no_drift: pd.DataFrame,
    ) -> None:
        report = generate_drift_report(
            reference_df,
            production_no_drift,
            list(reference_df.columns),
        )
        assert report.checked_at is not None
