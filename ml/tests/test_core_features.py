"""Tests for ml.features.core_features (the six scoring moat features)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ml.features.base import FeatureCategory, FeatureResult
from ml.features.core_features import (
    ALL_CORE_FEATURES,
    CBLRIComputer,
    DDCRatioComputer,
    GOSIndexComputer,
    NIQScoreComputer,
    SCFVComputer,
    UTDIComputer,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def cblri_df() -> pd.DataFrame:
    """Input data for CBLRI computation."""
    return pd.DataFrame({
        "cross_border_volume_q1": [10_000, 5_000],
        "cross_border_volume_q2": [12_000, 5_500],
        "cross_border_volume_q3": [11_000, 4_800],
        "cross_border_volume_q4": [10_500, 5_200],
        "cross_border_tx_count_q1": [5, 2],
        "cross_border_tx_count_q2": [6, 3],
        "cross_border_tx_count_q3": [5, 2],
        "cross_border_tx_count_q4": [7, 1],
        "unique_corridors": [5, 1],
    })


@pytest.fixture()
def utdi_df() -> pd.DataFrame:
    """Input data for UTDI computation."""
    return pd.DataFrame({
        "merchant_categories_q1": [10, 2],
        "merchant_categories_q2": [12, 3],
        "merchant_categories_q3": [11, 2],
        "merchant_categories_q4": [10, 1],
        "total_merchant_categories": [15, 4],
    })


@pytest.fixture()
def scfv_df() -> pd.DataFrame:
    """Input data for SCFV computation."""
    return pd.DataFrame({
        "digitized_links_current": [20, 5],
        "digitized_links_6m_ago": [10, 5],
        "total_trade_relationships": [30, 10],
        "invoices_digitized_pct": [80, 20],
    })


@pytest.fixture()
def ddc_df() -> pd.DataFrame:
    """Input data for DDC Ratio computation."""
    return pd.DataFrame({
        "tasks_completed": [45, 10],
        "tasks_assigned": [50, 30],
        "avg_completion_days": [3, 15],
        "tasks_overdue": [2, 8],
    })


@pytest.fixture()
def niq_df() -> pd.DataFrame:
    """Input data for NIQ Score computation."""
    return pd.DataFrame({
        "partner_score_1": [750, 400],
        "partner_score_2": [680, np.nan],
        "partner_score_3": [720, np.nan],
        "partner_score_4": [800, np.nan],
        "partner_score_5": [690, np.nan],
    })


@pytest.fixture()
def gos_df() -> pd.DataFrame:
    """Input data for GOS Index computation."""
    return pd.DataFrame({
        "gps_variance_km": [2.0, 50.0],
        "primary_location_tx_pct": [85, 20],
        "unique_transaction_locations": [3, 30],
    })


# ---------------------------------------------------------------------------
# Tests — CBLRI
# ---------------------------------------------------------------------------


class TestCBLRI:
    def test_basic_computation(self, cblri_df: pd.DataFrame) -> None:
        computer = CBLRIComputer()
        result = computer.compute(cblri_df)

        assert isinstance(result, FeatureResult)
        assert result.metadata.name == "cblri"
        assert result.metadata.category == FeatureCategory.CORE
        assert len(result.values) == 2
        # Values should be in [0, 1]
        assert (result.values >= 0.0).all()
        assert (result.values <= 1.0).all()

    def test_consistent_flows_score_higher(self, cblri_df: pd.DataFrame) -> None:
        computer = CBLRIComputer()
        result = computer.compute(cblri_df)
        # Entity 0 has more corridors and more consistent volumes
        assert result.values.iloc[0] > result.values.iloc[1]

    def test_missing_columns(self) -> None:
        df = pd.DataFrame({"unrelated": [1, 2]})
        computer = CBLRIComputer()
        result = computer.compute(df)
        assert result.data_quality_score == 0.0
        assert result.values.isna().all()


# ---------------------------------------------------------------------------
# Tests — UTDI
# ---------------------------------------------------------------------------


class TestUTDI:
    def test_basic_computation(self, utdi_df: pd.DataFrame) -> None:
        computer = UTDIComputer()
        result = computer.compute(utdi_df)

        assert result.metadata.name == "utdi"
        assert len(result.values) == 2
        assert (result.values >= 0.0).all()
        assert (result.values <= 1.0).all()

    def test_diverse_entity_scores_higher(self, utdi_df: pd.DataFrame) -> None:
        computer = UTDIComputer()
        result = computer.compute(utdi_df)
        # Entity 0 has ~10-12 categories vs entity 1 with ~1-3
        assert result.values.iloc[0] > result.values.iloc[1]


# ---------------------------------------------------------------------------
# Tests — SCFV
# ---------------------------------------------------------------------------


class TestSCFV:
    def test_basic_computation(self, scfv_df: pd.DataFrame) -> None:
        computer = SCFVComputer()
        result = computer.compute(scfv_df)

        assert result.metadata.name == "scfv"
        assert len(result.values) == 2
        assert (result.values >= 0.0).all()
        assert (result.values <= 1.0).all()

    def test_growing_entity_scores_higher(self, scfv_df: pd.DataFrame) -> None:
        computer = SCFVComputer()
        result = computer.compute(scfv_df)
        # Entity 0 doubled links (10->20) with 80% invoice digitization
        # Entity 1 stayed at 5 with only 20% digitization
        assert result.values.iloc[0] > result.values.iloc[1]


# ---------------------------------------------------------------------------
# Tests — DDC Ratio
# ---------------------------------------------------------------------------


class TestDDCRatio:
    def test_basic_computation(self, ddc_df: pd.DataFrame) -> None:
        computer = DDCRatioComputer()
        result = computer.compute(ddc_df)

        assert result.metadata.name == "ddc_ratio"
        assert len(result.values) == 2
        assert (result.values >= 0.0).all()
        assert (result.values <= 1.0).all()

    def test_compliant_entity_scores_higher(self, ddc_df: pd.DataFrame) -> None:
        computer = DDCRatioComputer()
        result = computer.compute(ddc_df)
        # Entity 0: 90% completion, fast, few overdue
        # Entity 1: 33% completion, slow, many overdue
        assert result.values.iloc[0] > result.values.iloc[1]


# ---------------------------------------------------------------------------
# Tests — NIQ Score
# ---------------------------------------------------------------------------


class TestNIQScore:
    def test_basic_computation(self, niq_df: pd.DataFrame) -> None:
        computer = NIQScoreComputer()
        result = computer.compute(niq_df)

        assert result.metadata.name == "niq_score"
        assert len(result.values) == 2
        assert (result.values >= 0.0).all()
        assert (result.values <= 100.0).all()

    def test_strong_network_scores_higher(self, niq_df: pd.DataFrame) -> None:
        computer = NIQScoreComputer()
        result = computer.compute(niq_df)
        # Entity 0 has 5 partners with scores 680-800
        # Entity 1 has only 1 partner with score 400
        assert result.values.iloc[0] > result.values.iloc[1]

    def test_no_partners_zero_score(self) -> None:
        df = pd.DataFrame({
            "partner_score_1": [np.nan],
            "partner_score_2": [np.nan],
            "partner_score_3": [np.nan],
            "partner_score_4": [np.nan],
            "partner_score_5": [np.nan],
        })
        computer = NIQScoreComputer()
        result = computer.compute(df)
        assert result.values.iloc[0] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Tests — GOS Index
# ---------------------------------------------------------------------------


class TestGOSIndex:
    def test_basic_computation(self, gos_df: pd.DataFrame) -> None:
        computer = GOSIndexComputer()
        result = computer.compute(gos_df)

        assert result.metadata.name == "gos_index"
        assert len(result.values) == 2
        assert (result.values >= 0.0).all()
        assert (result.values <= 1.0).all()

    def test_stable_location_scores_higher(self, gos_df: pd.DataFrame) -> None:
        computer = GOSIndexComputer()
        result = computer.compute(gos_df)
        # Entity 0: low GPS variance (2km), 85% at primary, 3 locations
        # Entity 1: high GPS variance (50km), 20% at primary, 30 locations
        assert result.values.iloc[0] > result.values.iloc[1]


# ---------------------------------------------------------------------------
# Tests — Meta & Registry integration
# ---------------------------------------------------------------------------


class TestCoreFeaturesMeta:
    def test_all_features_listed(self) -> None:
        assert len(ALL_CORE_FEATURES) == 6

    def test_all_are_core_category(self) -> None:
        for cls in ALL_CORE_FEATURES:
            assert cls().metadata.category == FeatureCategory.CORE

    def test_feature_names(self) -> None:
        names = {cls().metadata.name for cls in ALL_CORE_FEATURES}
        expected = {"cblri", "utdi", "scfv", "ddc_ratio", "niq_score", "gos_index"}
        assert names == expected


class TestFeatureRegistry:
    def test_default_registry_count(self) -> None:
        from ml.features import create_default_registry

        registry = create_default_registry()
        # 8 transaction + 6 network + 6 supply chain + 5 compliance + 6 core = 31
        assert len(registry) == 31

    def test_get_by_name(self) -> None:
        from ml.features import create_default_registry

        registry = create_default_registry()
        computer = registry.get("cblri")
        assert computer.metadata.name == "cblri"

    def test_get_unknown_raises(self) -> None:
        from ml.features import create_default_registry

        registry = create_default_registry()
        with pytest.raises(KeyError, match="not_a_feature"):
            registry.get("not_a_feature")

    def test_by_category(self) -> None:
        from ml.features import FeatureCategory, create_default_registry

        registry = create_default_registry()
        tx_features = registry.by_category(FeatureCategory.TRANSACTION)
        assert len(tx_features) == 8

    def test_duplicate_registration_raises(self) -> None:
        from ml.features import FeatureRegistry

        registry = FeatureRegistry()
        computer = CBLRIComputer()
        registry.register(computer)
        with pytest.raises(ValueError, match="already registered"):
            registry.register(computer)

    def test_replace_allows_overwrite(self) -> None:
        from ml.features import FeatureRegistry

        registry = FeatureRegistry()
        registry.register(CBLRIComputer())
        registry.replace(CBLRIComputer())  # Should not raise
        assert len(registry) == 1

    def test_contains(self) -> None:
        from ml.features import create_default_registry

        registry = create_default_registry()
        assert "cblri" in registry
        assert "nonexistent" not in registry

    def test_metadata_table(self) -> None:
        from ml.features import create_default_registry

        registry = create_default_registry()
        table = registry.metadata_table()
        assert len(table) == 31
        assert all("name" in row for row in table)
        assert all("category" in row for row in table)
