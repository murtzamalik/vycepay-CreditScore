"""Feature freshness monitoring for VyceScore pipelines.

Tracks the age of features in the offline and online stores, raises
alerts when features exceed the 48-hour staleness threshold (BRD SLA).

Monitors:
    - Per-category average feature age.
    - Per-subject stale feature detection.
    - Overall freshness KPI (target: avg age < 48h).
    - Prometheus-compatible metric export.

Usage:
    python -m data_engineering.monitoring.feature_freshness
    python -m data_engineering.monitoring.feature_freshness --threshold-hours 24
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_STALENESS_THRESHOLD_HOURS = 48
FEATURE_CATEGORIES = [
    "transaction", "network", "supply_chain", "compliance", "core",
]


class AlertLevel(str, Enum):
    """Alert severity for freshness violations."""

    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class CategoryFreshness:
    """Freshness metrics for a single feature category."""

    category: str
    avg_age_hours: float
    max_age_hours: float
    min_age_hours: float
    total_subjects: int
    stale_subjects: int
    freshness_pct: float  # % of subjects with fresh features
    alert_level: AlertLevel = AlertLevel.OK

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "avg_age_hours": round(self.avg_age_hours, 2),
            "max_age_hours": round(self.max_age_hours, 2),
            "min_age_hours": round(self.min_age_hours, 2),
            "total_subjects": self.total_subjects,
            "stale_subjects": self.stale_subjects,
            "freshness_pct": round(self.freshness_pct, 4),
            "alert_level": self.alert_level.value,
        }


@dataclass
class FreshnessReport:
    """Aggregate freshness report across all categories."""

    overall_avg_age_hours: float = 0.0
    overall_freshness_pct: float = 0.0
    threshold_hours: float = DEFAULT_STALENESS_THRESHOLD_HOURS
    categories: list[CategoryFreshness] = field(default_factory=list)
    stale_alerts: list[dict[str, Any]] = field(default_factory=list)
    checked_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    overall_alert_level: AlertLevel = AlertLevel.OK

    @property
    def is_healthy(self) -> bool:
        """Overall system is healthy if avg age < threshold."""
        return self.overall_avg_age_hours < self.threshold_hours

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_avg_age_hours": round(self.overall_avg_age_hours, 2),
            "overall_freshness_pct": round(self.overall_freshness_pct, 4),
            "threshold_hours": self.threshold_hours,
            "is_healthy": self.is_healthy,
            "overall_alert_level": self.overall_alert_level.value,
            "checked_at": self.checked_at,
            "categories": [c.to_dict() for c in self.categories],
            "stale_alerts_count": len(self.stale_alerts),
        }

    def to_prometheus_metrics(self) -> str:
        """Export metrics in Prometheus text exposition format."""
        lines: list[str] = []
        lines.append(
            "# HELP vycescore_feature_avg_age_hours "
            "Average feature age in hours."
        )
        lines.append(
            "# TYPE vycescore_feature_avg_age_hours gauge"
        )
        lines.append(
            f"vycescore_feature_avg_age_hours "
            f"{self.overall_avg_age_hours:.2f}"
        )

        lines.append(
            "# HELP vycescore_feature_freshness_pct "
            "Percentage of features that are fresh."
        )
        lines.append(
            "# TYPE vycescore_feature_freshness_pct gauge"
        )
        lines.append(
            f"vycescore_feature_freshness_pct "
            f"{self.overall_freshness_pct:.4f}"
        )

        lines.append(
            "# HELP vycescore_feature_stale_count "
            "Number of stale feature alerts."
        )
        lines.append(
            "# TYPE vycescore_feature_stale_count gauge"
        )
        lines.append(
            f"vycescore_feature_stale_count "
            f"{len(self.stale_alerts)}"
        )

        for cat in self.categories:
            labels = f'category="{cat.category}"'
            lines.append(
                f'vycescore_feature_category_avg_age_hours{{{labels}}} '
                f'{cat.avg_age_hours:.2f}'
            )
            lines.append(
                f'vycescore_feature_category_stale_subjects{{{labels}}} '
                f'{cat.stale_subjects}'
            )

        return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Freshness checker
# ---------------------------------------------------------------------------

class FeatureFreshnessMonitor:
    """Monitor feature freshness across all categories.

    Reads feature metadata (computed_at timestamps) from the offline
    store partitions and computes staleness metrics.
    """

    def __init__(
        self,
        threshold_hours: float = DEFAULT_STALENESS_THRESHOLD_HOURS,
        *,
        warning_pct: float = 0.90,
        critical_pct: float = 0.75,
    ) -> None:
        """Initialize the monitor.

        Args:
            threshold_hours: Max allowed feature age in hours.
            warning_pct: Freshness percentage below which to warn.
            critical_pct: Freshness percentage below which is critical.
        """
        self.threshold_hours = threshold_hours
        self.warning_pct = warning_pct
        self.critical_pct = critical_pct

    def check_category_freshness(
        self,
        df: pd.DataFrame,
        category: str,
        *,
        reference_time: datetime | None = None,
    ) -> CategoryFreshness:
        """Check freshness for a single category's feature data.

        Args:
            df: Feature DataFrame with a 'computed_at' timestamp column.
            category: Category name.
            reference_time: Time to compare against (default: now UTC).

        Returns:
            CategoryFreshness metrics.
        """
        if reference_time is None:
            reference_time = datetime.now(timezone.utc)

        if df.empty or "computed_at" not in df.columns:
            return CategoryFreshness(
                category=category,
                avg_age_hours=float("inf"),
                max_age_hours=float("inf"),
                min_age_hours=float("inf"),
                total_subjects=0,
                stale_subjects=0,
                freshness_pct=0.0,
                alert_level=AlertLevel.CRITICAL,
            )

        computed_at = pd.to_datetime(df["computed_at"], utc=True)
        ref = pd.Timestamp(reference_time, tz="UTC")
        age_hours = (ref - computed_at).dt.total_seconds() / 3600.0

        total = len(age_hours)
        stale_mask = age_hours > self.threshold_hours
        stale_count = int(stale_mask.sum())
        fresh_pct = 1.0 - (stale_count / total) if total > 0 else 0.0

        alert = AlertLevel.OK
        if fresh_pct < self.critical_pct:
            alert = AlertLevel.CRITICAL
        elif fresh_pct < self.warning_pct:
            alert = AlertLevel.WARNING

        return CategoryFreshness(
            category=category,
            avg_age_hours=float(age_hours.mean()),
            max_age_hours=float(age_hours.max()),
            min_age_hours=float(age_hours.min()),
            total_subjects=total,
            stale_subjects=stale_count,
            freshness_pct=fresh_pct,
            alert_level=alert,
        )

    def find_stale_subjects(
        self,
        df: pd.DataFrame,
        category: str,
        *,
        reference_time: datetime | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Identify subjects with stale features.

        Args:
            df: Feature DataFrame with computed_at and national_id_hash.
            category: Category name for context.
            reference_time: Time to compare against.
            limit: Max number of stale subjects to return.

        Returns:
            List of stale subject records.
        """
        if reference_time is None:
            reference_time = datetime.now(timezone.utc)

        if df.empty or "computed_at" not in df.columns:
            return []

        computed_at = pd.to_datetime(df["computed_at"], utc=True)
        ref = pd.Timestamp(reference_time, tz="UTC")
        age_hours = (ref - computed_at).dt.total_seconds() / 3600.0

        stale_mask = age_hours > self.threshold_hours
        stale_df = df[stale_mask].head(limit).copy()
        stale_df["age_hours"] = age_hours[stale_mask].head(limit).values

        id_col = "national_id_hash" if "national_id_hash" in stale_df.columns else None

        alerts: list[dict[str, Any]] = []
        for _, row in stale_df.iterrows():
            alert: dict[str, Any] = {
                "category": category,
                "age_hours": round(float(row["age_hours"]), 2),
                "computed_at": str(row["computed_at"]),
            }
            if id_col:
                alert["national_id_hash"] = str(row[id_col])
            alerts.append(alert)

        return alerts

    def check_all_categories(
        self,
        category_data: dict[str, pd.DataFrame],
        *,
        reference_time: datetime | None = None,
    ) -> FreshnessReport:
        """Run freshness checks across all provided categories.

        Args:
            category_data: Mapping of category name to feature DataFrame.
            reference_time: Time to compare against (default: now UTC).

        Returns:
            FreshnessReport with overall and per-category metrics.
        """
        report = FreshnessReport(threshold_hours=self.threshold_hours)

        all_ages: list[float] = []
        total_subjects = 0
        total_stale = 0

        for category, df in category_data.items():
            cat_freshness = self.check_category_freshness(
                df, category, reference_time=reference_time,
            )
            report.categories.append(cat_freshness)

            if cat_freshness.total_subjects > 0:
                all_ages.append(cat_freshness.avg_age_hours)
                total_subjects += cat_freshness.total_subjects
                total_stale += cat_freshness.stale_subjects

            # Collect stale alerts
            stale = self.find_stale_subjects(
                df, category, reference_time=reference_time,
            )
            report.stale_alerts.extend(stale)

        if all_ages:
            report.overall_avg_age_hours = sum(all_ages) / len(all_ages)
        else:
            report.overall_avg_age_hours = float("inf")

        if total_subjects > 0:
            report.overall_freshness_pct = (
                1.0 - total_stale / total_subjects
            )
        else:
            report.overall_freshness_pct = 0.0

        # Set overall alert level
        if report.overall_freshness_pct < self.critical_pct:
            report.overall_alert_level = AlertLevel.CRITICAL
        elif report.overall_freshness_pct < self.warning_pct:
            report.overall_alert_level = AlertLevel.WARNING
        else:
            report.overall_alert_level = AlertLevel.OK

        return report


def load_feature_metadata(
    category: str,
    processing_date: str,
    *,
    base_path: str | None = None,
) -> pd.DataFrame:
    """Load feature data with computed_at timestamps for freshness check.

    Args:
        category: Feature category name.
        processing_date: Date partition to load.
        base_path: Optional override for feature store path.

    Returns:
        DataFrame with at least computed_at column.
    """
    if base_path is None:
        datalake = os.getenv(
            "VYCESCORE_DATALAKE_PATH", "s3a://vycescore-datalake"
        )
        base_path = f"{datalake}/features/{category}"

    path = f"{base_path}/dt={processing_date}"
    try:
        return pd.read_parquet(path)
    except Exception as exc:
        logger.warning(
            "Could not load feature data for %s at %s: %s",
            category, path, exc,
        )
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    """Run feature freshness monitoring from the command line."""
    import argparse

    parser = argparse.ArgumentParser(
        description="VyceScore Feature Freshness Monitor"
    )
    parser.add_argument(
        "--date",
        default=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        help="Date partition to check (default: today)",
    )
    parser.add_argument(
        "--threshold-hours",
        type=float,
        default=DEFAULT_STALENESS_THRESHOLD_HOURS,
        help=f"Staleness threshold in hours (default: {DEFAULT_STALENESS_THRESHOLD_HOURS})",
    )
    parser.add_argument(
        "--prometheus",
        action="store_true",
        help="Output Prometheus-format metrics",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    monitor = FeatureFreshnessMonitor(threshold_hours=args.threshold_hours)
    category_data: dict[str, pd.DataFrame] = {}

    for category in FEATURE_CATEGORIES:
        category_data[category] = load_feature_metadata(
            category, args.date
        )

    report = monitor.check_all_categories(category_data)

    if args.prometheus:
        print(report.to_prometheus_metrics())
    else:
        import json
        print(json.dumps(report.to_dict(), indent=2))


if __name__ == "__main__":
    main()
