"""Tests for feature freshness monitoring (Task 5.8)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from data_engineering.monitoring.feature_freshness import (
    AlertLevel,
    CategoryFreshness,
    FeatureFreshnessMonitor,
    FreshnessReport,
)


class TestCategoryFreshness:
    """Tests for CategoryFreshness dataclass."""

    def test_to_dict(self) -> None:
        cf = CategoryFreshness(
            category="transaction",
            avg_age_hours=12.5,
            max_age_hours=24.0,
            min_age_hours=1.0,
            total_subjects=100,
            stale_subjects=5,
            freshness_pct=0.95,
            alert_level=AlertLevel.OK,
        )
        d = cf.to_dict()
        assert d["category"] == "transaction"
        assert d["avg_age_hours"] == 12.5


class TestFreshnessReport:
    """Tests for FreshnessReport dataclass."""

    def test_is_healthy_when_fresh(self) -> None:
        report = FreshnessReport(
            overall_avg_age_hours=24.0,
            threshold_hours=48.0,
        )
        assert report.is_healthy is True

    def test_is_unhealthy_when_stale(self) -> None:
        report = FreshnessReport(
            overall_avg_age_hours=72.0,
            threshold_hours=48.0,
        )
        assert report.is_healthy is False

    def test_to_prometheus_metrics(self) -> None:
        report = FreshnessReport(
            overall_avg_age_hours=20.0,
            overall_freshness_pct=0.95,
            categories=[
                CategoryFreshness(
                    category="transaction",
                    avg_age_hours=15.0,
                    max_age_hours=30.0,
                    min_age_hours=2.0,
                    total_subjects=100,
                    stale_subjects=3,
                    freshness_pct=0.97,
                ),
            ],
        )
        metrics = report.to_prometheus_metrics()
        assert "vycescore_feature_avg_age_hours" in metrics
        assert "vycescore_feature_freshness_pct" in metrics
        assert 'category="transaction"' in metrics

    def test_to_dict(self) -> None:
        report = FreshnessReport(
            overall_avg_age_hours=20.0,
            overall_freshness_pct=0.95,
        )
        d = report.to_dict()
        assert "is_healthy" in d
        assert d["is_healthy"] is True


class TestFeatureFreshnessMonitor:
    """Tests for FeatureFreshnessMonitor."""

    def test_check_category_freshness_all_fresh(self) -> None:
        monitor = FeatureFreshnessMonitor(threshold_hours=48)
        now = datetime.now(timezone.utc)
        df = pd.DataFrame({
            "national_id_hash": ["a" * 64, "b" * 64],
            "computed_at": [
                now - timedelta(hours=6),
                now - timedelta(hours=12),
            ],
        })

        result = monitor.check_category_freshness(
            df, "transaction", reference_time=now,
        )
        assert result.stale_subjects == 0
        assert result.freshness_pct == 1.0
        assert result.alert_level == AlertLevel.OK

    def test_check_category_freshness_some_stale(self) -> None:
        monitor = FeatureFreshnessMonitor(threshold_hours=48)
        now = datetime.now(timezone.utc)
        df = pd.DataFrame({
            "national_id_hash": ["a" * 64, "b" * 64, "c" * 64],
            "computed_at": [
                now - timedelta(hours=6),
                now - timedelta(hours=72),
                now - timedelta(hours=96),
            ],
        })

        result = monitor.check_category_freshness(
            df, "transaction", reference_time=now,
        )
        assert result.stale_subjects == 2
        assert result.total_subjects == 3

    def test_check_category_freshness_empty_df(self) -> None:
        monitor = FeatureFreshnessMonitor()
        result = monitor.check_category_freshness(
            pd.DataFrame(), "transaction",
        )
        assert result.alert_level == AlertLevel.CRITICAL
        assert result.total_subjects == 0

    def test_find_stale_subjects(self) -> None:
        monitor = FeatureFreshnessMonitor(threshold_hours=24)
        now = datetime.now(timezone.utc)
        df = pd.DataFrame({
            "national_id_hash": ["a" * 64, "b" * 64],
            "computed_at": [
                now - timedelta(hours=6),
                now - timedelta(hours=48),
            ],
        })

        stale = monitor.find_stale_subjects(
            df, "core", reference_time=now,
        )
        assert len(stale) == 1
        assert stale[0]["category"] == "core"

    def test_check_all_categories(self) -> None:
        monitor = FeatureFreshnessMonitor(threshold_hours=48)
        now = datetime.now(timezone.utc)

        data = {
            "transaction": pd.DataFrame({
                "computed_at": [now - timedelta(hours=12)],
            }),
            "core": pd.DataFrame({
                "computed_at": [now - timedelta(hours=24)],
            }),
        }

        report = monitor.check_all_categories(
            data, reference_time=now,
        )
        assert len(report.categories) == 2
        assert report.is_healthy is True
        assert report.overall_alert_level == AlertLevel.OK

    def test_alert_levels(self) -> None:
        monitor = FeatureFreshnessMonitor(
            threshold_hours=24,
            warning_pct=0.90,
            critical_pct=0.50,
        )
        now = datetime.now(timezone.utc)

        # All stale -> critical
        df = pd.DataFrame({
            "computed_at": [now - timedelta(hours=48)] * 10,
        })
        result = monitor.check_category_freshness(
            df, "test", reference_time=now,
        )
        assert result.alert_level == AlertLevel.CRITICAL
