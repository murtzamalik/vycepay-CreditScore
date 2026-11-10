"""Tests for ml.features.supply_chain_features."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ml.features.base import FeatureCategory, FeatureResult
from ml.features.supply_chain_features import (
    ALL_SUPPLY_CHAIN_FEATURES,
    CustomerConcentration,
    DaysPayableOutstanding,
    InvoiceCollectionDays,
    SupplierDiversification,
    SupplierPaymentPunctuality,
    SupplyChainDepth,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def supply_chain_df() -> pd.DataFrame:
    """Pre-aggregated supply chain data per entity."""
    return pd.DataFrame({
        "entity_id": ["E001", "E002", "E003", "E004"],
        "on_time_payments": [90.0, 45.0, 0.0, np.nan],
        "total_supplier_payments": [100.0, 50.0, 0.0, np.nan],
        "avg_collection_days": [15.0, 45.0, 0.0, np.nan],
        "supply_chain_tiers": [3, 1, 2, np.nan],
        "active_supplier_count": [12, 5, 0, np.nan],
        "avg_days_payable": [30.0, 60.0, 0.0, np.nan],
        "customer_concentration_hhi": [0.15, 0.80, 1.0, np.nan],
    })


@pytest.fixture()
def customer_revenue_df() -> pd.DataFrame:
    """Per-customer revenue data for HHI calculation."""
    return pd.DataFrame({
        "entity_id": [
            "E001", "E001", "E001", "E001",
            "E002", "E002",
        ],
        "customer_id": [
            "C1", "C2", "C3", "C4",
            "C1", "C2",
        ],
        "revenue": [
            25_000, 25_000, 25_000, 25_000,
            90_000, 10_000,
        ],
    })


# ---------------------------------------------------------------------------
# Tests — SupplierPaymentPunctuality
# ---------------------------------------------------------------------------


class TestSupplierPaymentPunctuality:
    def test_basic_computation(self, supply_chain_df: pd.DataFrame) -> None:
        computer = SupplierPaymentPunctuality()
        result = computer.compute(supply_chain_df)

        assert isinstance(result, FeatureResult)
        assert result.metadata.name == "supplier_payment_punctuality"
        assert result.metadata.category == FeatureCategory.SUPPLY_CHAIN
        # E001: 90/100 = 0.9
        assert result.values.iloc[0] == pytest.approx(0.9)
        # E002: 45/50 = 0.9
        assert result.values.iloc[1] == pytest.approx(0.9)

    def test_zero_total_returns_nan(self) -> None:
        df = pd.DataFrame({
            "on_time_payments": [10.0],
            "total_supplier_payments": [0.0],
        })
        computer = SupplierPaymentPunctuality()
        result = computer.compute(df)
        assert np.isnan(result.values.iloc[0])

    def test_clamped_to_unit_interval(self) -> None:
        df = pd.DataFrame({
            "on_time_payments": [120.0],
            "total_supplier_payments": [100.0],
        })
        computer = SupplierPaymentPunctuality()
        result = computer.compute(df)
        assert result.values.iloc[0] <= 1.0

    def test_missing_columns(self) -> None:
        df = pd.DataFrame({"unrelated": [1]})
        computer = SupplierPaymentPunctuality()
        result = computer.compute(df)
        assert result.data_quality_score == 0.0


# ---------------------------------------------------------------------------
# Tests — InvoiceCollectionDays
# ---------------------------------------------------------------------------


class TestInvoiceCollectionDays:
    def test_basic_computation(self, supply_chain_df: pd.DataFrame) -> None:
        computer = InvoiceCollectionDays()
        result = computer.compute(supply_chain_df)

        assert result.values.iloc[0] == 15.0
        assert result.values.iloc[1] == 45.0

    def test_negative_clipped(self) -> None:
        df = pd.DataFrame({"avg_collection_days": [-5.0, 10.0]})
        computer = InvoiceCollectionDays()
        result = computer.compute(df)
        assert result.values.iloc[0] == 0.0


# ---------------------------------------------------------------------------
# Tests — SupplyChainDepth
# ---------------------------------------------------------------------------


class TestSupplyChainDepth:
    def test_basic_computation(self, supply_chain_df: pd.DataFrame) -> None:
        computer = SupplyChainDepth()
        result = computer.compute(supply_chain_df)

        assert result.values.iloc[0] == 3.0
        assert result.values.iloc[1] == 1.0


# ---------------------------------------------------------------------------
# Tests — CustomerConcentration
# ---------------------------------------------------------------------------


class TestCustomerConcentration:
    def test_hhi_from_revenue_data(
        self, customer_revenue_df: pd.DataFrame
    ) -> None:
        computer = CustomerConcentration()
        result = computer.compute(customer_revenue_df)

        # E001: 4 equal customers => HHI = 4 * (0.25)^2 = 0.25
        assert result.values["E001"] == pytest.approx(0.25)
        # E002: 90k/100k=0.9, 10k/100k=0.1 => 0.81 + 0.01 = 0.82
        assert result.values["E002"] == pytest.approx(0.82)

    def test_hhi_from_pre_aggregated(
        self, supply_chain_df: pd.DataFrame
    ) -> None:
        computer = CustomerConcentration()
        result = computer.compute(supply_chain_df)

        assert result.values.iloc[0] == pytest.approx(0.15)
        assert result.values.iloc[1] == pytest.approx(0.80)

    def test_single_customer_hhi_is_one(self) -> None:
        df = pd.DataFrame({
            "entity_id": ["E001"],
            "customer_id": ["C1"],
            "revenue": [100_000],
        })
        computer = CustomerConcentration()
        result = computer.compute(df)
        assert result.values["E001"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Tests — SupplierDiversification
# ---------------------------------------------------------------------------


class TestSupplierDiversification:
    def test_basic_computation(self, supply_chain_df: pd.DataFrame) -> None:
        computer = SupplierDiversification()
        result = computer.compute(supply_chain_df)
        assert result.values.iloc[0] == 12.0
        assert result.values.iloc[1] == 5.0


# ---------------------------------------------------------------------------
# Tests — DaysPayableOutstanding
# ---------------------------------------------------------------------------


class TestDaysPayableOutstanding:
    def test_basic_computation(self, supply_chain_df: pd.DataFrame) -> None:
        computer = DaysPayableOutstanding()
        result = computer.compute(supply_chain_df)
        assert result.values.iloc[0] == 30.0
        assert result.values.iloc[1] == 60.0


# ---------------------------------------------------------------------------
# Tests — Meta
# ---------------------------------------------------------------------------


class TestSupplyChainFeaturesMeta:
    def test_all_features_listed(self) -> None:
        assert len(ALL_SUPPLY_CHAIN_FEATURES) == 6

    def test_all_are_supply_chain_category(self) -> None:
        for cls in ALL_SUPPLY_CHAIN_FEATURES:
            assert cls().metadata.category == FeatureCategory.SUPPLY_CHAIN
