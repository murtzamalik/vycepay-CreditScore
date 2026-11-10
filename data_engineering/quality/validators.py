"""Data quality validators for VyceScore pipelines.

Provides composable validation checks for transaction, supply chain,
and feature data. Each validator returns a ``ValidationResult`` with
pass/fail status, metrics, and diagnostic details.

Design goals:
    - No external dependency on Great Expectations at runtime (custom
      validators that can be used in Airflow tasks or standalone).
    - Configurable thresholds (completeness target >= 95%).
    - Machine-readable reports for downstream alerting.

Usage::

    from data_engineering.quality.validators import (
        DataQualityValidator,
        TransactionValidator,
        FeatureValidator,
    )

    validator = TransactionValidator()
    result = validator.validate(df)
    assert result.passed
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Sequence

import pandas as pd

logger = logging.getLogger(__name__)


class Severity(str, Enum):
    """Severity level for a validation check."""

    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


@dataclass
class CheckResult:
    """Result of a single validation check."""

    check_name: str
    passed: bool
    severity: Severity
    metric_value: float | None = None
    threshold: float | None = None
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """Aggregate result of all validation checks on a dataset."""

    validator_name: str
    passed: bool
    checks: list[CheckResult] = field(default_factory=list)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    row_count: int = 0
    column_count: int = 0

    @property
    def critical_failures(self) -> list[CheckResult]:
        """Return checks that failed at critical severity."""
        return [
            c for c in self.checks
            if not c.passed and c.severity == Severity.CRITICAL
        ]

    @property
    def warnings(self) -> list[CheckResult]:
        """Return checks that failed at warning severity."""
        return [
            c for c in self.checks
            if not c.passed and c.severity == Severity.WARNING
        ]

    @property
    def pass_rate(self) -> float:
        """Fraction of checks that passed."""
        if not self.checks:
            return 0.0
        return sum(1 for c in self.checks if c.passed) / len(self.checks)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "validator_name": self.validator_name,
            "passed": self.passed,
            "pass_rate": round(self.pass_rate, 4),
            "row_count": self.row_count,
            "column_count": self.column_count,
            "timestamp": self.timestamp,
            "critical_failures": len(self.critical_failures),
            "warnings": len(self.warnings),
            "checks": [
                {
                    "check_name": c.check_name,
                    "passed": c.passed,
                    "severity": c.severity.value,
                    "metric_value": c.metric_value,
                    "threshold": c.threshold,
                    "message": c.message,
                }
                for c in self.checks
            ],
        }


class DataQualityValidator:
    """Base validator with reusable check primitives."""

    def __init__(self, name: str = "base") -> None:
        self.name = name

    # -- Primitive checks ---------------------------------------------------

    def check_not_null(
        self,
        df: pd.DataFrame,
        column: str,
        *,
        severity: Severity = Severity.CRITICAL,
    ) -> CheckResult:
        """Check that a column has no null values."""
        if column not in df.columns:
            return CheckResult(
                check_name=f"not_null:{column}",
                passed=False,
                severity=severity,
                message=f"Column '{column}' does not exist",
            )
        null_count = int(df[column].isna().sum())
        total = len(df)
        null_pct = null_count / total if total > 0 else 0.0
        passed = null_count == 0
        return CheckResult(
            check_name=f"not_null:{column}",
            passed=passed,
            severity=severity,
            metric_value=1.0 - null_pct,
            threshold=1.0,
            message=f"{null_count}/{total} null values ({null_pct:.2%})",
        )

    def check_completeness(
        self,
        df: pd.DataFrame,
        column: str,
        *,
        threshold: float = 0.95,
        severity: Severity = Severity.WARNING,
    ) -> CheckResult:
        """Check that a column meets the completeness threshold (>= threshold non-null)."""
        if column not in df.columns:
            return CheckResult(
                check_name=f"completeness:{column}",
                passed=False,
                severity=severity,
                metric_value=0.0,
                threshold=threshold,
                message=f"Column '{column}' does not exist",
            )
        total = len(df)
        if total == 0:
            return CheckResult(
                check_name=f"completeness:{column}",
                passed=False,
                severity=severity,
                metric_value=0.0,
                threshold=threshold,
                message="DataFrame is empty",
            )
        non_null = int(df[column].notna().sum())
        completeness = non_null / total
        passed = completeness >= threshold
        return CheckResult(
            check_name=f"completeness:{column}",
            passed=passed,
            severity=severity,
            metric_value=round(completeness, 4),
            threshold=threshold,
            message=f"Completeness {completeness:.2%} (threshold {threshold:.0%})",
        )

    def check_range(
        self,
        df: pd.DataFrame,
        column: str,
        *,
        min_value: float | None = None,
        max_value: float | None = None,
        severity: Severity = Severity.WARNING,
    ) -> CheckResult:
        """Check that all values in a column fall within [min_value, max_value]."""
        if column not in df.columns:
            return CheckResult(
                check_name=f"range:{column}",
                passed=False,
                severity=severity,
                message=f"Column '{column}' does not exist",
            )
        series = df[column].dropna()
        if len(series) == 0:
            return CheckResult(
                check_name=f"range:{column}",
                passed=True,
                severity=severity,
                message="No non-null values to check",
            )
        violations = 0
        if min_value is not None:
            violations += int((series < min_value).sum())
        if max_value is not None:
            violations += int((series > max_value).sum())
        passed = violations == 0
        return CheckResult(
            check_name=f"range:{column}",
            passed=passed,
            severity=severity,
            metric_value=float(violations),
            threshold=0.0,
            message=f"{violations} values out of range [{min_value}, {max_value}]",
        )

    def check_uniqueness(
        self,
        df: pd.DataFrame,
        column: str,
        *,
        severity: Severity = Severity.CRITICAL,
    ) -> CheckResult:
        """Check that all values in a column are unique."""
        if column not in df.columns:
            return CheckResult(
                check_name=f"unique:{column}",
                passed=False,
                severity=severity,
                message=f"Column '{column}' does not exist",
            )
        total = len(df)
        unique_count = df[column].nunique()
        duplicates = total - unique_count
        passed = duplicates == 0
        return CheckResult(
            check_name=f"unique:{column}",
            passed=passed,
            severity=severity,
            metric_value=float(duplicates),
            threshold=0.0,
            message=f"{duplicates} duplicate values",
        )

    def check_values_in_set(
        self,
        df: pd.DataFrame,
        column: str,
        allowed_values: set[Any],
        *,
        severity: Severity = Severity.WARNING,
    ) -> CheckResult:
        """Check that all values belong to an allowed set."""
        if column not in df.columns:
            return CheckResult(
                check_name=f"in_set:{column}",
                passed=False,
                severity=severity,
                message=f"Column '{column}' does not exist",
            )
        series = df[column].dropna()
        invalid = series[~series.isin(allowed_values)]
        passed = len(invalid) == 0
        return CheckResult(
            check_name=f"in_set:{column}",
            passed=passed,
            severity=severity,
            metric_value=float(len(invalid)),
            threshold=0.0,
            message=f"{len(invalid)} values not in allowed set",
            details={"sample_invalid": list(invalid.head(5).values)} if not passed else {},
        )

    def check_row_count(
        self,
        df: pd.DataFrame,
        *,
        min_rows: int = 1,
        max_rows: int | None = None,
        severity: Severity = Severity.CRITICAL,
    ) -> CheckResult:
        """Check that the DataFrame has an expected number of rows."""
        total = len(df)
        passed = total >= min_rows
        if max_rows is not None:
            passed = passed and total <= max_rows
        return CheckResult(
            check_name="row_count",
            passed=passed,
            severity=severity,
            metric_value=float(total),
            threshold=float(min_rows),
            message=f"{total} rows (expected >= {min_rows})",
        )

    def check_regex(
        self,
        df: pd.DataFrame,
        column: str,
        pattern: str,
        *,
        severity: Severity = Severity.WARNING,
    ) -> CheckResult:
        """Check that all values in a column match a regex pattern."""
        if column not in df.columns:
            return CheckResult(
                check_name=f"regex:{column}",
                passed=False,
                severity=severity,
                message=f"Column '{column}' does not exist",
            )
        series = df[column].dropna().astype(str)
        matches = series.str.match(pattern)
        violations = int((~matches).sum())
        passed = violations == 0
        return CheckResult(
            check_name=f"regex:{column}",
            passed=passed,
            severity=severity,
            metric_value=float(violations),
            threshold=0.0,
            message=f"{violations} values do not match pattern '{pattern}'",
        )

    def _build_result(self, checks: list[CheckResult]) -> ValidationResult:
        """Build a ValidationResult from a list of check results.

        The overall result passes only when no critical checks have failed.
        """
        critical_failures = [
            c for c in checks
            if not c.passed and c.severity == Severity.CRITICAL
        ]
        return ValidationResult(
            validator_name=self.name,
            passed=len(critical_failures) == 0,
            checks=checks,
        )


class TransactionValidator(DataQualityValidator):
    """Validator for VycePay transaction data."""

    REQUIRED_COLUMNS: list[str] = [
        "transaction_id",
        "national_id_hash",
        "transaction_type",
        "amount",
        "currency",
        "timestamp",
        "is_cross_border",
    ]

    ALLOWED_TX_TYPES: set[str] = {
        "FT", "IBFT", "REMIT", "MERCHANT", "BILL_PAY", "CASH_IN", "CASH_OUT",
    }

    ALLOWED_CURRENCIES: set[str] = {
        "KES", "USD", "EUR", "GBP", "UGX", "TZS", "RWF", "ETB",
    }

    def __init__(self) -> None:
        super().__init__(name="transaction_validator")

    def validate(self, df: pd.DataFrame) -> ValidationResult:
        """Run all transaction data quality checks.

        Args:
            df: Transaction DataFrame to validate.

        Returns:
            ValidationResult with all check outcomes.
        """
        checks: list[CheckResult] = []

        # Row count
        checks.append(self.check_row_count(df, min_rows=1))

        # Not-null checks on critical columns
        for col in self.REQUIRED_COLUMNS:
            checks.append(self.check_not_null(df, col))

        # Uniqueness
        checks.append(self.check_uniqueness(df, "transaction_id"))

        # Value ranges
        checks.append(self.check_range(
            df, "amount",
            min_value=0.01, max_value=50_000_000.0,
            severity=Severity.CRITICAL,
        ))

        # Enum checks
        checks.append(self.check_values_in_set(
            df, "transaction_type", self.ALLOWED_TX_TYPES,
        ))
        checks.append(self.check_values_in_set(
            df, "currency", self.ALLOWED_CURRENCIES,
        ))

        # Format check: national_id_hash should be 64-char hex
        checks.append(self.check_regex(
            df, "national_id_hash", r"^[a-f0-9]{64}$",
            severity=Severity.CRITICAL,
        ))

        # Completeness for optional columns
        for col in ["merchant_category_code", "counterparty_hash", "latitude", "longitude"]:
            checks.append(self.check_completeness(
                df, col, threshold=0.50, severity=Severity.INFO,
            ))

        result = self._build_result(checks)
        result.row_count = len(df)
        result.column_count = len(df.columns)
        return result


class SupplyChainValidator(DataQualityValidator):
    """Validator for VyceTrade supply chain data."""

    REQUIRED_COLUMNS: list[str] = [
        "link_id",
        "supplier_hash",
        "buyer_hash",
        "is_digitized",
        "registration_date",
    ]

    def __init__(self) -> None:
        super().__init__(name="supply_chain_validator")

    def validate(self, df: pd.DataFrame) -> ValidationResult:
        """Run all supply chain data quality checks."""
        checks: list[CheckResult] = []

        checks.append(self.check_row_count(df, min_rows=1))

        for col in self.REQUIRED_COLUMNS:
            checks.append(self.check_not_null(df, col))

        checks.append(self.check_uniqueness(df, "link_id"))
        checks.append(self.check_values_in_set(
            df, "is_digitized", {0, 1},
            severity=Severity.CRITICAL,
        ))

        # Completeness for invoice columns
        for col in ["invoice_count", "total_invoice_value"]:
            checks.append(self.check_completeness(
                df, col, threshold=0.80, severity=Severity.WARNING,
            ))

        result = self._build_result(checks)
        result.row_count = len(df)
        result.column_count = len(df.columns)
        return result


class FeatureValidator(DataQualityValidator):
    """Validator for computed feature vectors.

    Validates that computed features fall within expected ranges
    per the BRD specification.
    """

    FEATURE_RANGES: dict[str, tuple[float, float]] = {
        "cblri": (0.0, 1.0),
        "utdi": (0.0, 1.0),
        "scfv": (0.0, 1.0),
        "ddc_ratio": (0.0, 1.0),
        "niq_score": (0.0, 100.0),
        "gos_index": (0.0, 1.0),
        "tx_volume_30d": (0.0, 1e9),
        "tx_value_30d": (0.0, 1e12),
        "tx_volume_volatility": (0.0, 100.0),
        "incoming_outgoing_ratio": (0.0, 1e6),
        "avg_transaction_size": (0.0, 50_000_000.0),
        "max_single_transaction": (0.0, 50_000_000.0),
        "days_since_last_tx": (0.0, 3650.0),
        "unique_counterparties_30d": (0.0, 1e6),
        "network_degree": (0.0, 1e6),
        "network_clustering": (0.0, 1.0),
        "network_betweenness": (0.0, 1.0),
        "reciprocal_relationships": (0.0, 1e6),
        "merchant_diversity": (0.0, 100.0),
        "high_activity_neighbors": (0.0, 1e6),
        "supplier_payment_punctuality": (0.0, 1.0),
        "invoice_collection_days": (0.0, 3650.0),
        "supply_chain_depth": (0.0, 100.0),
        "customer_concentration": (0.0, 1.0),
        "supplier_diversification": (0.0, 1e6),
        "days_payable_outstanding": (0.0, 3650.0),
        "kyc_verification_days": (0.0, 3650.0),
        "aml_risk_score": (0.0, 1.0),
        "identity_match_confidence": (0.0, 1.0),
        "sanctions_list_flag": (0.0, 1.0),
        "pep_flag": (0.0, 1.0),
    }

    def __init__(self) -> None:
        super().__init__(name="feature_validator")

    def validate(self, df: pd.DataFrame) -> ValidationResult:
        """Run all feature quality checks."""
        checks: list[CheckResult] = []

        checks.append(self.check_row_count(df, min_rows=1))

        # Check national_id_hash
        checks.append(self.check_not_null(df, "national_id_hash"))

        # Validate each feature present in the dataframe
        for feature_name, (min_val, max_val) in self.FEATURE_RANGES.items():
            if feature_name in df.columns:
                checks.append(self.check_completeness(
                    df, feature_name, threshold=0.95,
                ))
                checks.append(self.check_range(
                    df, feature_name,
                    min_value=min_val, max_value=max_val,
                    severity=Severity.WARNING,
                ))

        result = self._build_result(checks)
        result.row_count = len(df)
        result.column_count = len(df.columns)
        return result


def generate_quality_report(
    results: Sequence[ValidationResult],
) -> dict[str, Any]:
    """Generate a consolidated data quality report from multiple validators.

    Args:
        results: List of ValidationResult from different validators.

    Returns:
        Consolidated report dictionary.
    """
    total_checks = sum(len(r.checks) for r in results)
    total_passed = sum(
        sum(1 for c in r.checks if c.passed) for r in results
    )
    critical_failures = sum(len(r.critical_failures) for r in results)
    all_passed = all(r.passed for r in results)

    return {
        "overall_passed": all_passed,
        "total_checks": total_checks,
        "checks_passed": total_passed,
        "pass_rate": round(total_passed / total_checks, 4) if total_checks > 0 else 0.0,
        "critical_failures": critical_failures,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "validators": [r.to_dict() for r in results],
    }
