"""Tests for ml.vod.signals — VOD distress signal calculations."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ml.vod.signals import (
    VODThresholds,
    compute_cblri,
    compute_cblri_drop_percent,
    compute_gos_index,
    compute_gos_volatility,
    compute_signals_from_dataframe,
    compute_tx_pattern_zscore,
    compute_vod_flag,
)


# ===================================================================
# GOS Index
# ===================================================================


class TestComputeGOSIndex:
    """Tests for compute_gos_index."""

    def test_scalar_net_inflow(self) -> None:
        result = compute_gos_index(100.0, 50.0)
        assert isinstance(result, float)
        assert result == pytest.approx(50.0 / 150.0)

    def test_scalar_net_outflow(self) -> None:
        result = compute_gos_index(20.0, 80.0)
        assert result == pytest.approx(-60.0 / 100.0)

    def test_scalar_balanced(self) -> None:
        result = compute_gos_index(50.0, 50.0)
        assert result == pytest.approx(0.0)

    def test_zero_activity(self) -> None:
        """Both zero => denominator floors at 1.0, result is 0."""
        result = compute_gos_index(0.0, 0.0)
        assert result == pytest.approx(0.0)

    def test_range_is_bounded(self) -> None:
        """GOS should be in [-1, 1]."""
        assert compute_gos_index(1000.0, 0.0) == pytest.approx(1.0)
        assert compute_gos_index(0.0, 1000.0) == pytest.approx(-1.0)

    def test_numpy_array_input(self) -> None:
        incoming = np.array([100.0, 0.0, 50.0])
        outgoing = np.array([50.0, 100.0, 50.0])
        result = compute_gos_index(incoming, outgoing)
        assert isinstance(result, np.ndarray)
        expected = np.array([50 / 150, -1.0, 0.0])
        np.testing.assert_allclose(result, expected)

    def test_pandas_series_input(self) -> None:
        incoming = pd.Series([100.0, 0.0], index=["a", "b"])
        outgoing = pd.Series([50.0, 100.0], index=["a", "b"])
        result = compute_gos_index(incoming, outgoing)
        assert isinstance(result, pd.Series)
        assert list(result.index) == ["a", "b"]

    def test_negative_values_clipped(self) -> None:
        """Negative tx values should be clipped to 0 with a warning."""
        result = compute_gos_index(-10.0, 50.0)
        # Treated as incoming=0, outgoing=50 => -50/50 = -1.0
        assert result == pytest.approx(-1.0)

    def test_small_denominator_protected(self) -> None:
        """Very small values should not cause division issues."""
        result = compute_gos_index(0.001, 0.001)
        # sum = 0.002, floored to 1.0, so result = 0/1 = 0
        assert result == pytest.approx(0.0)


class TestComputeGOSVolatility:
    """Tests for compute_gos_volatility."""

    def test_stable_values(self) -> None:
        values = [0.2, 0.2, 0.2, 0.2, 0.2]
        assert compute_gos_volatility(values) == pytest.approx(0.0)

    def test_volatile_values(self) -> None:
        values = [0.5, -0.5, 0.5, -0.5, 0.5, -0.5]
        result = compute_gos_volatility(values)
        assert result > 0.4  # High volatility expected

    def test_single_value_returns_zero(self) -> None:
        assert compute_gos_volatility([0.3]) == 0.0

    def test_empty_returns_zero(self) -> None:
        assert compute_gos_volatility([]) == 0.0

    def test_handles_nan(self) -> None:
        values = [0.2, float("nan"), 0.2, 0.2]
        result = compute_gos_volatility(values)
        assert result == pytest.approx(0.0)  # All valid values are 0.2

    def test_uses_sample_std(self) -> None:
        """Should use ddof=1 (sample standard deviation)."""
        values = [0.0, 1.0]
        result = compute_gos_volatility(values)
        expected = np.std([0.0, 1.0], ddof=1)
        assert result == pytest.approx(expected)


# ===================================================================
# CBLRI
# ===================================================================


class TestComputeCBLRI:
    """Tests for compute_cblri."""

    def test_improving_liquidity(self) -> None:
        result = compute_cblri(15_000.0, 10_000.0)
        assert result == pytest.approx(1.5)

    def test_deteriorating_liquidity(self) -> None:
        result = compute_cblri(5_000.0, 10_000.0)
        assert result == pytest.approx(0.5)

    def test_stable_liquidity(self) -> None:
        result = compute_cblri(10_000.0, 10_000.0)
        assert result == pytest.approx(1.0)

    def test_zero_denominator_floored(self) -> None:
        result = compute_cblri(5_000.0, 0.0)
        # 5000/1 = 5000, clamped to 5.0
        assert result == pytest.approx(5.0)

    def test_clamped_at_five(self) -> None:
        result = compute_cblri(100_000.0, 1.0)
        assert result == 5.0

    def test_negative_clipped(self) -> None:
        result = compute_cblri(-100.0, 1000.0)
        assert result >= 0.0

    def test_array_input(self) -> None:
        b30 = np.array([15_000.0, 5_000.0])
        b90 = np.array([10_000.0, 10_000.0])
        result = compute_cblri(b30, b90)
        np.testing.assert_allclose(result, [1.5, 0.5])


class TestComputeCBLRIDropPercent:
    """Tests for compute_cblri_drop_percent."""

    def test_no_drop(self) -> None:
        result = compute_cblri_drop_percent(1.2, 1.0)
        assert result == pytest.approx(0.0)  # Current > historical

    def test_thirty_percent_drop(self) -> None:
        result = compute_cblri_drop_percent(0.7, 1.0)
        assert result == pytest.approx(0.3)

    def test_full_drop(self) -> None:
        result = compute_cblri_drop_percent(0.0, 1.0)
        assert result == pytest.approx(1.0)

    def test_zero_historical(self) -> None:
        """Should not crash; denominator floored to 0.001."""
        result = compute_cblri_drop_percent(0.0, 0.0)
        assert np.isfinite(result)

    def test_improvement_returns_zero(self) -> None:
        """If current > historical, drop is 0 (not negative)."""
        result = compute_cblri_drop_percent(2.0, 1.0)
        assert result == pytest.approx(0.0)


# ===================================================================
# Transaction Pattern Z-Score
# ===================================================================


class TestComputeTxPatternZscore:
    """Tests for compute_tx_pattern_zscore."""

    def test_at_mean(self) -> None:
        result = compute_tx_pattern_zscore(40.0, 40.0, 8.0)
        assert result == pytest.approx(0.0)

    def test_one_std_above(self) -> None:
        result = compute_tx_pattern_zscore(48.0, 40.0, 8.0)
        assert result == pytest.approx(1.0)

    def test_two_std_below(self) -> None:
        """Should return absolute value."""
        result = compute_tx_pattern_zscore(24.0, 40.0, 8.0)
        assert result == pytest.approx(2.0)

    def test_zero_std_returns_zero(self) -> None:
        """No variance => can't measure deviation."""
        result = compute_tx_pattern_zscore(50.0, 40.0, 0.0)
        assert result == pytest.approx(0.0)

    def test_capped_at_ten(self) -> None:
        result = compute_tx_pattern_zscore(1000.0, 40.0, 1.0)
        assert result == 10.0

    def test_array_input(self) -> None:
        current = np.array([48.0, 24.0])
        mean = np.array([40.0, 40.0])
        std = np.array([8.0, 8.0])
        result = compute_tx_pattern_zscore(current, mean, std)
        np.testing.assert_allclose(result, [1.0, 2.0])


# ===================================================================
# Combined VOD Flag
# ===================================================================


class TestComputeVODFlag:
    """Tests for compute_vod_flag."""

    def test_no_distress(self) -> None:
        result = compute_vod_flag(0.1, 0.1, 1.0)
        assert result is False

    def test_gos_volatility_trigger(self) -> None:
        result = compute_vod_flag(0.5, 0.1, 1.0)
        assert result is True

    def test_cblri_drop_trigger(self) -> None:
        result = compute_vod_flag(0.1, 0.5, 1.0)
        assert result is True

    def test_zscore_trigger(self) -> None:
        result = compute_vod_flag(0.1, 0.1, 3.0)
        assert result is True

    def test_all_triggers(self) -> None:
        result = compute_vod_flag(0.5, 0.5, 3.0)
        assert result is True

    def test_custom_thresholds(self) -> None:
        strict = VODThresholds(
            gos_volatility=0.1,
            cblri_drop_pct=0.1,
            tx_pattern_zscore=1.0,
        )
        # Would be fine with defaults, but triggers with strict thresholds
        result = compute_vod_flag(0.15, 0.05, 0.5, thresholds=strict)
        assert result is True

    def test_array_input(self) -> None:
        gos = np.array([0.1, 0.5, 0.1])
        cblri = np.array([0.1, 0.1, 0.5])
        zscore = np.array([1.0, 1.0, 1.0])
        result = compute_vod_flag(gos, cblri, zscore)
        np.testing.assert_array_equal(result, [False, True, True])


# ===================================================================
# DataFrame batch processing
# ===================================================================


class TestComputeSignalsFromDataFrame:
    """Tests for compute_signals_from_dataframe."""

    def test_all_signal_columns_present(self, batch_dataframe: pd.DataFrame) -> None:
        result = compute_signals_from_dataframe(batch_dataframe)
        expected_cols = {
            "gos_index",
            "cblri",
            "cblri_drop_pct",
            "tx_pattern_zscore",
            "gos_volatility",
            "vod_flag",
            "has_sufficient_history",
        }
        assert expected_cols.issubset(set(result.columns))

    def test_preserves_original_columns(
        self, batch_dataframe: pd.DataFrame
    ) -> None:
        result = compute_signals_from_dataframe(batch_dataframe)
        for col in batch_dataframe.columns:
            assert col in result.columns

    def test_gos_index_bounded(self, batch_dataframe: pd.DataFrame) -> None:
        result = compute_signals_from_dataframe(batch_dataframe)
        assert (result["gos_index"] >= -1.0).all()
        assert (result["gos_index"] <= 1.0).all()

    def test_vod_flag_is_boolean(self, batch_dataframe: pd.DataFrame) -> None:
        result = compute_signals_from_dataframe(batch_dataframe)
        assert result["vod_flag"].dtype == bool

    def test_no_gos_period_columns(self) -> None:
        """Without gos_period_* columns, volatility defaults to 0."""
        df = pd.DataFrame(
            {
                "incoming_tx_value_30d": [100.0],
                "outgoing_tx_value_30d": [50.0],
                "avg_daily_balance_30d": [10_000.0],
                "avg_daily_balance_90d": [9_000.0],
                "historical_cblri": [1.0],
                "tx_count_current": [40.0],
                "tx_count_mean": [40.0],
                "tx_count_std": [5.0],
                "history_days": [90],
            }
        )
        result = compute_signals_from_dataframe(df)
        assert result["gos_volatility"].iloc[0] == 0.0

    def test_history_days_check(self) -> None:
        df = pd.DataFrame(
            {
                "incoming_tx_value_30d": [100.0, 100.0],
                "outgoing_tx_value_30d": [50.0, 50.0],
                "avg_daily_balance_30d": [10_000.0, 10_000.0],
                "avg_daily_balance_90d": [9_000.0, 9_000.0],
                "historical_cblri": [1.0, 1.0],
                "tx_count_current": [40.0, 40.0],
                "tx_count_mean": [40.0, 40.0],
                "tx_count_std": [5.0, 5.0],
                "history_days": [90, 10],
            }
        )
        result = compute_signals_from_dataframe(df)
        assert bool(result["has_sufficient_history"].iloc[0]) is True
        assert bool(result["has_sufficient_history"].iloc[1]) is False


# ===================================================================
# Threshold configuration
# ===================================================================


class TestVODThresholds:
    """Tests for VODThresholds dataclass."""

    def test_defaults(self) -> None:
        t = VODThresholds()
        assert t.gos_volatility == 0.35
        assert t.cblri_drop_pct == 0.30
        assert t.tx_pattern_zscore == 2.0
        assert t.min_history_days == 30
        assert t.gos_rolling_window == 6

    def test_custom_values(self) -> None:
        t = VODThresholds(gos_volatility=0.5, cblri_drop_pct=0.4)
        assert t.gos_volatility == 0.5
        assert t.cblri_drop_pct == 0.4

    def test_frozen(self) -> None:
        t = VODThresholds()
        with pytest.raises(AttributeError):
            t.gos_volatility = 0.5  # type: ignore[misc]
