"""Tests for data retention automation (Task 5.9)."""

from __future__ import annotations

import os
import tempfile
from datetime import date, timedelta

import pandas as pd
import pytest

from data_engineering.jobs.data_retention import (
    RETENTION_YEARS,
    STAGING_RETENTION_DAYS,
    RetentionAction,
    RetentionReport,
    anonymize_partition,
    anonymize_pii_columns,
    delete_partition,
    discover_partitions,
    get_anonymization_cutoff,
    get_retention_cutoff,
    parse_partition_date,
    run_retention_job,
)


class TestDateHelpers:
    """Tests for date calculation functions."""

    def test_retention_cutoff(self) -> None:
        ref = date(2026, 3, 8)
        cutoff = get_retention_cutoff(ref)
        expected = ref - timedelta(days=RETENTION_YEARS * 365)
        assert cutoff == expected

    def test_anonymization_cutoff(self) -> None:
        ref = date(2026, 3, 8)
        cutoff = get_anonymization_cutoff(ref)
        expected = ref - timedelta(days=STAGING_RETENTION_DAYS)
        assert cutoff == expected

    def test_parse_partition_date_valid(self) -> None:
        result = parse_partition_date("dt=2026-03-08")
        assert result == date(2026, 3, 8)

    def test_parse_partition_date_with_path(self) -> None:
        result = parse_partition_date("/data/staged/dt=2025-01-15/")
        assert result == date(2025, 1, 15)

    def test_parse_partition_date_invalid(self) -> None:
        assert parse_partition_date("not-a-partition") is None

    def test_parse_partition_date_bad_date(self) -> None:
        assert parse_partition_date("dt=2026-13-45") is None


class TestAnonymizePiiColumns:
    """Tests for PII anonymization."""

    def test_anonymizes_pii_columns(self) -> None:
        df = pd.DataFrame({
            "national_id": ["12345678", "87654321"],
            "phone_number": ["+254700000001", "+254700000002"],
            "amount": [1000.0, 2000.0],
        })
        result, count = anonymize_pii_columns(
            df, pii_columns=["national_id", "phone_number"],
        )
        assert count == 4
        assert "***ANONYMIZED***" in result["national_id"].iloc[0]
        assert "***ANONYMIZED***" in result["phone_number"].iloc[0]
        # Non-PII columns unchanged
        assert result["amount"].iloc[0] == 1000.0

    def test_preserves_nulls(self) -> None:
        df = pd.DataFrame({
            "national_id": ["12345678", None],
            "other": [1, 2],
        })
        result, count = anonymize_pii_columns(
            df, pii_columns=["national_id"],
        )
        assert count == 1
        assert pd.isna(result["national_id"].iloc[1])

    def test_skips_missing_columns(self) -> None:
        df = pd.DataFrame({"amount": [1000.0]})
        result, count = anonymize_pii_columns(
            df, pii_columns=["national_id"],
        )
        assert count == 0

    def test_original_df_not_modified(self) -> None:
        df = pd.DataFrame({"national_id": ["12345678"]})
        original_val = df["national_id"].iloc[0]
        anonymize_pii_columns(df, pii_columns=["national_id"])
        assert df["national_id"].iloc[0] == original_val


class TestDiscoverPartitions:
    """Tests for partition discovery."""

    def test_discovers_date_partitions(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "dt=2026-03-01"))
            os.makedirs(os.path.join(tmpdir, "dt=2026-03-02"))
            os.makedirs(os.path.join(tmpdir, "not-a-partition"))

            partitions = discover_partitions(tmpdir)
            assert len(partitions) == 2

    def test_nonexistent_path_returns_empty(self) -> None:
        partitions = discover_partitions("/nonexistent/path")
        assert partitions == []

    def test_sorted_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "dt=2026-03-02"))
            os.makedirs(os.path.join(tmpdir, "dt=2026-03-01"))

            partitions = discover_partitions(tmpdir)
            assert "dt=2026-03-01" in partitions[0]


class TestAnonymizePartition:
    """Tests for single partition anonymization."""

    def test_anonymize_partition_with_pii(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            partition_path = os.path.join(tmpdir, "dt=2026-02-01")
            os.makedirs(partition_path)

            df = pd.DataFrame({
                "national_id": ["12345", "67890"],
                "amount": [100.0, 200.0],
            })
            df.to_parquet(
                os.path.join(partition_path, "data.parquet"),
                index=False,
            )

            action = anonymize_partition(
                partition_path,
                pii_columns=["national_id"],
            )
            assert action.action_type == "anonymize"
            assert action.rows_affected == 2

    def test_dry_run_does_not_modify(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            partition_path = os.path.join(tmpdir, "dt=2026-02-01")
            os.makedirs(partition_path)

            df = pd.DataFrame({"national_id": ["12345"]})
            parquet_path = os.path.join(partition_path, "data.parquet")
            df.to_parquet(parquet_path, index=False)

            action = anonymize_partition(
                partition_path,
                dry_run=True,
                pii_columns=["national_id"],
            )
            assert action.action_type == "anonymize"
            assert "DRY RUN" in action.details

            # Verify original data is unchanged
            loaded = pd.read_parquet(parquet_path)
            assert loaded["national_id"].iloc[0] == "12345"


class TestDeletePartition:
    """Tests for partition deletion."""

    def test_delete_partition(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            partition_path = os.path.join(tmpdir, "dt=2016-01-01")
            os.makedirs(partition_path)
            open(os.path.join(partition_path, "data.parquet"), "w").close()

            action = delete_partition(partition_path)
            assert action.action_type == "delete"
            assert not os.path.exists(partition_path)

    def test_dry_run_does_not_delete(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            partition_path = os.path.join(tmpdir, "dt=2016-01-01")
            os.makedirs(partition_path)

            action = delete_partition(partition_path, dry_run=True)
            assert action.action_type == "delete"
            assert "DRY RUN" in action.details
            assert os.path.exists(partition_path)


class TestRunRetentionJob:
    """Tests for the full retention job."""

    def test_empty_paths_produce_clean_report(self) -> None:
        report = run_retention_job(
            reference_date=date(2026, 3, 8),
            anonymization_paths=["/nonexistent"],
            retention_paths=["/nonexistent"],
        )
        assert isinstance(report, RetentionReport)
        assert report.partitions_anonymized == 0
        assert report.partitions_deleted == 0

    def test_dry_run_flag(self) -> None:
        report = run_retention_job(
            reference_date=date(2026, 3, 8),
            dry_run=True,
            anonymization_paths=[],
            retention_paths=[],
        )
        assert report.dry_run is True

    def test_report_to_dict(self) -> None:
        report = RetentionReport(run_date="2026-03-08")
        d = report.to_dict()
        assert d["run_date"] == "2026-03-08"
        assert "actions" in d
