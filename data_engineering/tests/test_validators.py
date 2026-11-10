"""Tests for data quality validators (Task 5.5)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from data_engineering.quality.validators import (
    CheckResult,
    DataQualityValidator,
    FeatureValidator,
    Severity,
    SupplyChainValidator,
    TransactionValidator,
    ValidationResult,
    generate_quality_report,
)


class TestCheckResult:
    """Tests for CheckResult dataclass."""

    def test_check_result_creation(self) -> None:
        result = CheckResult(
            check_name="test", passed=True, severity=Severity.INFO,
        )
        assert result.passed is True
        assert result.severity == Severity.INFO


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_critical_failures_property(self) -> None:
        result = ValidationResult(
            validator_name="test",
            passed=False,
            checks=[
                CheckResult("c1", passed=False, severity=Severity.CRITICAL),
                CheckResult("c2", passed=True, severity=Severity.WARNING),
                CheckResult("c3", passed=False, severity=Severity.WARNING),
            ],
        )
        assert len(result.critical_failures) == 1
        assert len(result.warnings) == 1

    def test_pass_rate(self) -> None:
        result = ValidationResult(
            validator_name="test",
            passed=True,
            checks=[
                CheckResult("c1", passed=True, severity=Severity.INFO),
                CheckResult("c2", passed=False, severity=Severity.INFO),
            ],
        )
        assert result.pass_rate == 0.5

    def test_to_dict(self) -> None:
        result = ValidationResult(
            validator_name="test",
            passed=True,
            checks=[],
        )
        d = result.to_dict()
        assert d["validator_name"] == "test"
        assert d["passed"] is True
        assert "timestamp" in d


class TestDataQualityValidator:
    """Tests for base validator check primitives."""

    def setup_method(self) -> None:
        self.validator = DataQualityValidator("test")

    def test_check_not_null_passes(self) -> None:
        df = pd.DataFrame({"col": [1, 2, 3]})
        result = self.validator.check_not_null(df, "col")
        assert result.passed is True

    def test_check_not_null_fails(self) -> None:
        df = pd.DataFrame({"col": [1, None, 3]})
        result = self.validator.check_not_null(df, "col")
        assert result.passed is False

    def test_check_not_null_missing_column(self) -> None:
        df = pd.DataFrame({"other": [1]})
        result = self.validator.check_not_null(df, "missing")
        assert result.passed is False

    def test_check_completeness_passes(self) -> None:
        df = pd.DataFrame({"col": [1, 2, 3, 4, None]})
        result = self.validator.check_completeness(df, "col", threshold=0.75)
        assert result.passed is True

    def test_check_completeness_fails(self) -> None:
        df = pd.DataFrame({"col": [1, None, None, None, None]})
        result = self.validator.check_completeness(df, "col", threshold=0.95)
        assert result.passed is False

    def test_check_range_passes(self) -> None:
        df = pd.DataFrame({"col": [0.1, 0.5, 0.9]})
        result = self.validator.check_range(
            df, "col", min_value=0.0, max_value=1.0,
        )
        assert result.passed is True

    def test_check_range_fails(self) -> None:
        df = pd.DataFrame({"col": [0.1, 1.5, 0.9]})
        result = self.validator.check_range(
            df, "col", min_value=0.0, max_value=1.0,
        )
        assert result.passed is False

    def test_check_uniqueness_passes(self) -> None:
        df = pd.DataFrame({"col": [1, 2, 3]})
        result = self.validator.check_uniqueness(df, "col")
        assert result.passed is True

    def test_check_uniqueness_fails(self) -> None:
        df = pd.DataFrame({"col": [1, 1, 3]})
        result = self.validator.check_uniqueness(df, "col")
        assert result.passed is False

    def test_check_values_in_set_passes(self) -> None:
        df = pd.DataFrame({"col": ["A", "B", "C"]})
        result = self.validator.check_values_in_set(
            df, "col", {"A", "B", "C", "D"},
        )
        assert result.passed is True

    def test_check_values_in_set_fails(self) -> None:
        df = pd.DataFrame({"col": ["A", "X", "C"]})
        result = self.validator.check_values_in_set(
            df, "col", {"A", "B", "C"},
        )
        assert result.passed is False

    def test_check_row_count_passes(self) -> None:
        df = pd.DataFrame({"col": [1, 2, 3]})
        result = self.validator.check_row_count(df, min_rows=1)
        assert result.passed is True

    def test_check_row_count_fails(self) -> None:
        df = pd.DataFrame({"col": []})
        result = self.validator.check_row_count(df, min_rows=1)
        assert result.passed is False

    def test_check_regex_passes(self) -> None:
        df = pd.DataFrame({"col": ["abc123", "def456"]})
        result = self.validator.check_regex(df, "col", r"^[a-z]+\d+$")
        assert result.passed is True

    def test_check_regex_fails(self) -> None:
        df = pd.DataFrame({"col": ["abc", "123"]})
        result = self.validator.check_regex(df, "col", r"^[a-z]+\d+$")
        assert result.passed is False


class TestTransactionValidator:
    """Tests for TransactionValidator."""

    def test_valid_transactions_pass(self, sample_transactions: pd.DataFrame) -> None:
        validator = TransactionValidator()
        result = validator.validate(sample_transactions)
        assert result.row_count == len(sample_transactions)
        # All critical checks should pass for well-formed data
        assert len(result.critical_failures) == 0

    def test_empty_dataframe_fails(self) -> None:
        validator = TransactionValidator()
        df = pd.DataFrame(
            columns=TransactionValidator.REQUIRED_COLUMNS
        )
        result = validator.validate(df)
        assert result.passed is False

    def test_missing_transaction_id_fails(
        self, sample_transactions: pd.DataFrame,
    ) -> None:
        validator = TransactionValidator()
        df = sample_transactions.copy()
        df.loc[0, "transaction_id"] = None
        result = validator.validate(df)
        not_null_check = [
            c for c in result.checks
            if c.check_name == "not_null:transaction_id"
        ]
        assert len(not_null_check) == 1
        assert not_null_check[0].passed is False


class TestSupplyChainValidator:
    """Tests for SupplyChainValidator."""

    def test_valid_supply_chain_passes(
        self, sample_supply_chain: pd.DataFrame,
    ) -> None:
        validator = SupplyChainValidator()
        result = validator.validate(sample_supply_chain)
        assert result.row_count == len(sample_supply_chain)

    def test_empty_dataframe_fails(self) -> None:
        validator = SupplyChainValidator()
        df = pd.DataFrame(columns=SupplyChainValidator.REQUIRED_COLUMNS)
        result = validator.validate(df)
        assert result.passed is False


class TestFeatureValidator:
    """Tests for FeatureValidator."""

    def test_valid_features_pass(self, sample_features: pd.DataFrame) -> None:
        validator = FeatureValidator()
        result = validator.validate(sample_features)
        assert result.row_count == len(sample_features)

    def test_out_of_range_feature_warns(self) -> None:
        validator = FeatureValidator()
        df = pd.DataFrame({
            "national_id_hash": ["a" * 64],
            "cblri": [2.0],  # Out of [0, 1] range
        })
        result = validator.validate(df)
        range_checks = [
            c for c in result.checks if c.check_name == "range:cblri"
        ]
        assert len(range_checks) == 1
        assert range_checks[0].passed is False

    def test_covers_all_31_features(self) -> None:
        assert len(FeatureValidator.FEATURE_RANGES) >= 31


class TestGenerateQualityReport:
    """Tests for generate_quality_report."""

    def test_consolidated_report(self) -> None:
        results = [
            ValidationResult(
                validator_name="v1", passed=True,
                checks=[
                    CheckResult("c1", True, Severity.INFO),
                ],
            ),
            ValidationResult(
                validator_name="v2", passed=False,
                checks=[
                    CheckResult("c2", False, Severity.CRITICAL),
                ],
            ),
        ]
        report = generate_quality_report(results)
        assert report["overall_passed"] is False
        assert report["total_checks"] == 2
        assert report["checks_passed"] == 1
        assert report["critical_failures"] == 1
