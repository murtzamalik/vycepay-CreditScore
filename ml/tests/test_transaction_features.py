"""Tests for ml.features.transaction_features."""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from ml.features.base import FeatureCategory, FeatureResult
from ml.features.transaction_features import (
    ALL_TRANSACTION_FEATURES,
    AvgTransactionSize,
    DaysSinceLastTx,
    IncomingOutgoingRatio,
    MaxSingleTransaction,
    TxValue30d,
    TxVolume30d,
    TxVolumeVolatility,
    UniqueCounterparties30d,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def aggregated_tx_df() -> pd.DataFrame:
    """Pre-aggregated transaction data per entity."""
    return pd.DataFrame({
        "entity_id": ["E001", "E002", "E003", "E004"],
        "tx_total_value": [100_000.0, 50_000.0, 0.0, np.nan],
        "tx_total_count": [50.0, 25.0, 0.0, np.nan],
        "tx_count_in_window": [30, 15, 0, np.nan],
        "transaction_date": [
            datetime.now() - timedelta(days=5),
            datetime.now() - timedelta(days=40),
            datetime.now() - timedelta(days=10),
            pd.NaT,
        ],
        "max_tx_value": [20_000.0, 10_000.0, 0.0, np.nan],
        "last_transaction_date": [
            datetime.now() - timedelta(days=1),
            datetime.now() - timedelta(days=60),
            datetime.now() - timedelta(days=200),
            pd.NaT,
        ],
        "incoming_tx_count": [30.0, 10.0, 0.0, 5.0],
        "outgoing_tx_count": [20.0, 15.0, 0.0, 0.0],
        "unique_counterparties": [15.0, 8.0, 0.0, np.nan],
        # Monthly volumes for volatility
        "tx_count_m1": [40, 20, 5, 10],
        "tx_count_m2": [45, 22, 6, 12],
        "tx_count_m3": [38, 18, 4, 8],
        "tx_count_m4": [42, 25, 5, 11],
        "tx_count_m5": [50, 21, 7, 9],
        "tx_count_m6": [35, 19, 3, 10],
    })


# ---------------------------------------------------------------------------
# Tests — TxValue30d
# ---------------------------------------------------------------------------


class TestTxValue30d:
    def test_basic_computation(self, aggregated_tx_df: pd.DataFrame) -> None:
        computer = TxValue30d()
        result = computer.compute(aggregated_tx_df)

        assert isinstance(result, FeatureResult)
        assert result.metadata.name == "tx_value_30d"
        assert result.metadata.category == FeatureCategory.TRANSACTION
        assert result.values.iloc[0] == 100_000.0
        assert result.values.iloc[1] == 50_000.0
        assert result.values.iloc[2] == 0.0

    def test_negative_values_clipped(self) -> None:
        df = pd.DataFrame({"tx_total_value": [-100.0, 500.0]})
        computer = TxValue30d()
        result = computer.compute(df)
        assert result.values.iloc[0] == 0.0
        assert result.values.iloc[1] == 500.0

    def test_missing_column_returns_nan(self) -> None:
        df = pd.DataFrame({"unrelated": [1, 2, 3]})
        computer = TxValue30d()
        result = computer.compute(df)
        assert result.data_quality_score == 0.0
        assert result.values.isna().all()


# ---------------------------------------------------------------------------
# Tests — TxVolumeVolatility
# ---------------------------------------------------------------------------


class TestTxVolumeVolatility:
    def test_basic_computation(self, aggregated_tx_df: pd.DataFrame) -> None:
        computer = TxVolumeVolatility()
        result = computer.compute(aggregated_tx_df)

        assert isinstance(result, FeatureResult)
        assert result.metadata.name == "tx_volume_volatility"
        assert len(result.values) == len(aggregated_tx_df)
        # All values should be non-negative (CV is non-negative)
        valid = result.values.dropna()
        assert (valid >= 0).all()

    def test_constant_volume_zero_volatility(self) -> None:
        df = pd.DataFrame({
            "tx_count_m1": [10],
            "tx_count_m2": [10],
            "tx_count_m3": [10],
            "tx_count_m4": [10],
            "tx_count_m5": [10],
            "tx_count_m6": [10],
        })
        computer = TxVolumeVolatility()
        result = computer.compute(df)
        assert result.values.iloc[0] == pytest.approx(0.0, abs=1e-10)

    def test_missing_columns(self) -> None:
        df = pd.DataFrame({"tx_count_m1": [10]})
        computer = TxVolumeVolatility()
        result = computer.compute(df)
        assert result.data_quality_score == 0.0


# ---------------------------------------------------------------------------
# Tests — IncomingOutgoingRatio
# ---------------------------------------------------------------------------


class TestIncomingOutgoingRatio:
    def test_basic_computation(self, aggregated_tx_df: pd.DataFrame) -> None:
        computer = IncomingOutgoingRatio()
        result = computer.compute(aggregated_tx_df)

        assert result.metadata.name == "incoming_outgoing_ratio"
        # E001: 30/20 = 1.5
        assert result.values.iloc[0] == pytest.approx(1.5)
        # E002: 10/15 = 0.667
        assert result.values.iloc[1] == pytest.approx(10.0 / 15.0)

    def test_zero_outgoing_returns_nan(self, aggregated_tx_df: pd.DataFrame) -> None:
        computer = IncomingOutgoingRatio()
        result = computer.compute(aggregated_tx_df)
        # E004: 5/0 should be NaN (safe divide)
        assert np.isnan(result.values.iloc[3])


# ---------------------------------------------------------------------------
# Tests — AvgTransactionSize
# ---------------------------------------------------------------------------


class TestAvgTransactionSize:
    def test_basic_computation(self, aggregated_tx_df: pd.DataFrame) -> None:
        computer = AvgTransactionSize()
        result = computer.compute(aggregated_tx_df)

        assert result.metadata.name == "avg_transaction_size"
        # E001: 100000/50 = 2000
        assert result.values.iloc[0] == pytest.approx(2000.0)

    def test_zero_count_returns_nan(self) -> None:
        df = pd.DataFrame({
            "tx_total_value": [1000.0],
            "tx_total_count": [0.0],
        })
        computer = AvgTransactionSize()
        result = computer.compute(df)
        assert np.isnan(result.values.iloc[0])


# ---------------------------------------------------------------------------
# Tests — MaxSingleTransaction
# ---------------------------------------------------------------------------


class TestMaxSingleTransaction:
    def test_basic_computation(self, aggregated_tx_df: pd.DataFrame) -> None:
        computer = MaxSingleTransaction()
        result = computer.compute(aggregated_tx_df)
        assert result.values.iloc[0] == 20_000.0
        assert result.values.iloc[1] == 10_000.0


# ---------------------------------------------------------------------------
# Tests — DaysSinceLastTx
# ---------------------------------------------------------------------------


class TestDaysSinceLastTx:
    def test_basic_computation(self) -> None:
        ref = datetime(2025, 6, 15)
        df = pd.DataFrame({
            "last_transaction_date": [
                datetime(2025, 6, 14),
                datetime(2025, 6, 10),
                pd.NaT,
            ]
        })
        computer = DaysSinceLastTx()
        result = computer.compute(df, reference_date=ref)

        assert result.values.iloc[0] == pytest.approx(1.0)
        assert result.values.iloc[1] == pytest.approx(5.0)
        assert np.isnan(result.values.iloc[2])

    def test_future_date_returns_nan(self) -> None:
        ref = datetime(2025, 6, 15)
        df = pd.DataFrame({
            "last_transaction_date": [datetime(2025, 6, 20)]
        })
        computer = DaysSinceLastTx()
        result = computer.compute(df, reference_date=ref)
        assert np.isnan(result.values.iloc[0])


# ---------------------------------------------------------------------------
# Tests — UniqueCounterparties30d
# ---------------------------------------------------------------------------


class TestUniqueCounterparties30d:
    def test_basic_computation(self, aggregated_tx_df: pd.DataFrame) -> None:
        computer = UniqueCounterparties30d()
        result = computer.compute(aggregated_tx_df)
        assert result.values.iloc[0] == 15.0
        assert result.values.iloc[1] == 8.0


# ---------------------------------------------------------------------------
# Tests — Data quality & registry
# ---------------------------------------------------------------------------


class TestTransactionFeaturesMeta:
    def test_all_features_listed(self) -> None:
        assert len(ALL_TRANSACTION_FEATURES) == 8

    def test_all_are_transaction_category(self) -> None:
        for cls in ALL_TRANSACTION_FEATURES:
            assert cls().metadata.category == FeatureCategory.TRANSACTION

    def test_data_quality_perfect_data(self) -> None:
        df = pd.DataFrame({
            "tx_total_value": [100.0, 200.0],
            "tx_total_count": [10.0, 20.0],
        })
        computer = AvgTransactionSize()
        result = computer.compute(df)
        assert result.data_quality_score == pytest.approx(1.0)

    def test_data_quality_with_nulls(self) -> None:
        df = pd.DataFrame({
            "tx_total_value": [100.0, np.nan],
            "tx_total_count": [10.0, 20.0],
        })
        computer = AvgTransactionSize()
        result = computer.compute(df)
        # 3/4 cells non-null, sqrt(1.0 * 0.75) ~ 0.866
        assert 0.0 < result.data_quality_score < 1.0
