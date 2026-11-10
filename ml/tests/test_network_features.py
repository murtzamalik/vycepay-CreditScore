"""Tests for ml.features.network_features."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ml.features.base import FeatureCategory, FeatureResult
from ml.features.network_features import (
    ALL_NETWORK_FEATURES,
    HighActivityNeighbors,
    MerchantDiversity,
    NetworkBetweenness,
    NetworkClustering,
    NetworkDegree,
    ReciprocalRelationships,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def edge_df() -> pd.DataFrame:
    """Edge list representing a small transaction network.

    Network:
        A -- B -- C
        |       / |
        D -----   E

    A connects to B, D
    B connects to A, C
    C connects to B, D, E
    D connects to A, C
    E connects to C
    """
    return pd.DataFrame({
        "entity_id": ["A", "A", "B", "C", "C", "D"],
        "counterparty_id": ["B", "D", "C", "D", "E", "C"],
    })


@pytest.fixture()
def directed_edge_df() -> pd.DataFrame:
    """Directed edges with direction column for reciprocal testing."""
    return pd.DataFrame({
        "entity_id": ["A", "A", "B", "B", "C", "C", "D"],
        "counterparty_id": ["B", "C", "A", "C", "A", "B", "A"],
        "direction": [
            "outgoing", "outgoing",
            "outgoing", "outgoing",
            "outgoing", "outgoing",
            "outgoing",
        ],
    })


@pytest.fixture()
def merchant_df() -> pd.DataFrame:
    """Transaction data with merchant categories."""
    return pd.DataFrame({
        "entity_id": [
            "A", "A", "A", "A", "A",
            "B", "B",
            "C",
        ],
        "merchant_category": [
            "retail", "grocery", "retail", "transport", "utility",
            "retail", "retail",
            "grocery",
        ],
    })


@pytest.fixture()
def activity_df() -> pd.DataFrame:
    """Edge data with counterparty activity for high-activity testing."""
    return pd.DataFrame({
        "entity_id": ["A", "A", "A", "B", "B"],
        "counterparty_id": ["X", "Y", "Z", "X", "W"],
        "counterparty_tx_count": [100, 20, 60, 100, 5],
    })


# ---------------------------------------------------------------------------
# Tests — NetworkDegree
# ---------------------------------------------------------------------------


class TestNetworkDegree:
    def test_basic_degree(self, edge_df: pd.DataFrame) -> None:
        computer = NetworkDegree()
        result = computer.compute(edge_df)

        assert isinstance(result, FeatureResult)
        assert result.metadata.category == FeatureCategory.NETWORK
        # A connects to B, D => degree 2
        assert result.values["A"] == 2
        # C connects to B, D, E => degree 3
        assert result.values["C"] == 3

    def test_missing_columns(self) -> None:
        df = pd.DataFrame({"unrelated": [1]})
        computer = NetworkDegree()
        result = computer.compute(df)
        assert result.data_quality_score == 0.0
        assert result.values.isna().all()


# ---------------------------------------------------------------------------
# Tests — NetworkClustering
# ---------------------------------------------------------------------------


class TestNetworkClustering:
    def test_basic_clustering(self, edge_df: pd.DataFrame) -> None:
        computer = NetworkClustering()
        result = computer.compute(edge_df)

        assert isinstance(result, FeatureResult)
        # All values should be between 0 and 1
        assert (result.values >= 0.0).all()
        assert (result.values <= 1.0).all()

    def test_complete_graph_clustering(self) -> None:
        # Triangle: all nodes connected to each other -> clustering = 1.0
        df = pd.DataFrame({
            "entity_id": ["A", "A", "B"],
            "counterparty_id": ["B", "C", "C"],
        })
        computer = NetworkClustering()
        result = computer.compute(df)
        assert result.values["A"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Tests — NetworkBetweenness
# ---------------------------------------------------------------------------


class TestNetworkBetweenness:
    def test_basic_betweenness(self, edge_df: pd.DataFrame) -> None:
        computer = NetworkBetweenness()
        result = computer.compute(edge_df)

        assert isinstance(result, FeatureResult)
        assert (result.values >= 0.0).all()
        assert (result.values <= 1.0).all()

    def test_bridge_node_high_betweenness(self) -> None:
        # B is the bridge between A and C; all three are entity_ids
        df = pd.DataFrame({
            "entity_id": ["A", "B", "C"],
            "counterparty_id": ["B", "C", "B"],
        })
        computer = NetworkBetweenness()
        result = computer.compute(df)
        # B should have highest betweenness as the bridge
        assert result.values["B"] >= result.values["A"]
        assert result.values["B"] >= result.values["C"]


# ---------------------------------------------------------------------------
# Tests — ReciprocalRelationships
# ---------------------------------------------------------------------------


class TestReciprocalRelationships:
    def test_reciprocal_counting(self) -> None:
        # A sends to B (outgoing), B sends to A (incoming for A)
        df = pd.DataFrame({
            "entity_id": ["A", "A", "B", "C"],
            "counterparty_id": ["B", "C", "A", "D"],
            "direction": ["outgoing", "outgoing", "incoming", "outgoing"],
        })
        # For entity A: outgoing to {B, C}, incoming from {} -> 0 reciprocal
        # But we need incoming records for A
        df2 = pd.DataFrame({
            "entity_id": ["A", "A", "A", "B"],
            "counterparty_id": ["B", "C", "B", "A"],
            "direction": ["outgoing", "outgoing", "incoming", "outgoing"],
        })
        computer = ReciprocalRelationships()
        result = computer.compute(df2)
        # A: outgoing={B,C}, incoming={B} -> reciprocal with B -> 1
        assert result.values["A"] == 1

    def test_missing_direction_column(self) -> None:
        df = pd.DataFrame({
            "entity_id": ["A"],
            "counterparty_id": ["B"],
        })
        computer = ReciprocalRelationships()
        result = computer.compute(df)
        assert result.data_quality_score == 0.0


# ---------------------------------------------------------------------------
# Tests — MerchantDiversity
# ---------------------------------------------------------------------------


class TestMerchantDiversity:
    def test_basic_diversity(self, merchant_df: pd.DataFrame) -> None:
        computer = MerchantDiversity()
        result = computer.compute(merchant_df)

        assert isinstance(result, FeatureResult)
        # A has 4 categories (retail x2, grocery, transport, utility)
        # => Shannon entropy > 0
        assert result.values["A"] > 0
        # C has only 1 category => entropy = 0
        assert result.values["C"] == pytest.approx(0.0)
        # B has only retail => entropy = 0
        assert result.values["B"] == pytest.approx(0.0)

    def test_higher_diversity_higher_score(self, merchant_df: pd.DataFrame) -> None:
        computer = MerchantDiversity()
        result = computer.compute(merchant_df)
        # A (4 distinct categories) should have higher diversity than B (1 category)
        assert result.values["A"] > result.values["B"]


# ---------------------------------------------------------------------------
# Tests — HighActivityNeighbors
# ---------------------------------------------------------------------------


class TestHighActivityNeighbors:
    def test_basic_counting(self, activity_df: pd.DataFrame) -> None:
        computer = HighActivityNeighbors()
        result = computer.compute(activity_df, activity_threshold=50.0)

        # A: X(100>=50), Y(20<50), Z(60>=50) -> 2 high-activity neighbors
        assert result.values["A"] == 2.0
        # B: X(100>=50), W(5<50) -> 1 high-activity neighbor
        assert result.values["B"] == 1.0

    def test_high_threshold_no_neighbors(self, activity_df: pd.DataFrame) -> None:
        computer = HighActivityNeighbors()
        result = computer.compute(activity_df, activity_threshold=200.0)
        assert (result.values == 0).all()


# ---------------------------------------------------------------------------
# Tests — Meta
# ---------------------------------------------------------------------------


class TestNetworkFeaturesMeta:
    def test_all_features_listed(self) -> None:
        assert len(ALL_NETWORK_FEATURES) == 6

    def test_all_are_network_category(self) -> None:
        for cls in ALL_NETWORK_FEATURES:
            assert cls().metadata.category == FeatureCategory.NETWORK
