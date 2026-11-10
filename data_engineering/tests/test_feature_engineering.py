"""Tests for feature engineering job (Task 5.6)."""

from __future__ import annotations

import os
import tempfile

import pandas as pd
import pytest

from data_engineering.jobs.feature_engineering import (
    ALL_CATEGORIES,
    FeatureJobResult,
    load_category_data,
    parse_args,
    write_feature_output,
)


class TestFeatureJobResult:
    """Tests for FeatureJobResult dataclass."""

    def test_default_result(self) -> None:
        result = FeatureJobResult(processing_date="2026-03-08")
        assert result.processing_date == "2026-03-08"
        assert result.success is False
        assert result.features_computed == 0

    def test_to_dict(self) -> None:
        result = FeatureJobResult(
            processing_date="2026-03-08",
            categories_processed=["transaction"],
            features_computed=8,
            subjects_processed=100,
            success=True,
        )
        d = result.to_dict()
        assert d["processing_date"] == "2026-03-08"
        assert d["features_computed"] == 8
        assert d["success"] is True


class TestWriteFeatureOutput:
    """Tests for writing features to Parquet."""

    def test_write_creates_parquet_file(
        self, sample_features: pd.DataFrame,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = write_feature_output(
                sample_features,
                "transaction",
                "2026-03-08",
                base_path=tmpdir,
            )
            parquet_file = os.path.join(output_path, "features.parquet")
            assert os.path.exists(parquet_file)

            loaded = pd.read_parquet(parquet_file)
            assert len(loaded) == len(sample_features)

    def test_write_preserves_columns(
        self, sample_features: pd.DataFrame,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = write_feature_output(
                sample_features,
                "core",
                "2026-03-08",
                base_path=tmpdir,
            )
            loaded = pd.read_parquet(
                os.path.join(output_path, "features.parquet")
            )
            for col in sample_features.columns:
                assert col in loaded.columns


class TestLoadCategoryData:
    """Tests for loading category data."""

    def test_load_missing_data_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_category_data(
                "transaction",
                "2026-03-08",
                base_path="/nonexistent/path",
            )


class TestParseArgs:
    """Tests for CLI argument parsing."""

    def test_required_date(self) -> None:
        args = parse_args(["--date", "2026-03-08"])
        assert args.date == "2026-03-08"

    def test_missing_date_raises(self) -> None:
        with pytest.raises(SystemExit):
            parse_args([])

    def test_categories_filter(self) -> None:
        args = parse_args([
            "--date", "2026-03-08",
            "--categories", "transaction", "core",
        ])
        assert args.categories == ["transaction", "core"]

    def test_default_categories_is_none(self) -> None:
        args = parse_args(["--date", "2026-03-08"])
        assert args.categories is None

    def test_all_categories_constant(self) -> None:
        assert len(ALL_CATEGORIES) == 5
        assert "transaction" in ALL_CATEGORIES
        assert "core" in ALL_CATEGORIES
