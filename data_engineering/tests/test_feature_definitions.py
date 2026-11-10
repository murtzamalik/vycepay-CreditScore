"""Tests for Feast feature definitions (Task 5.1)."""

from __future__ import annotations

import pytest
from feast import Entity, FeatureView


class TestEntities:
    """Tests for Feast entity definitions."""

    def test_subject_entity_exists(self) -> None:
        from data_engineering.feature_store.feature_definitions import subject

        assert isinstance(subject, Entity)
        assert subject.name == "subject"

    def test_subject_join_keys(self) -> None:
        from data_engineering.feature_store.feature_definitions import subject

        assert subject.join_keys == ["national_id_hash"]

    def test_all_entities_list(self) -> None:
        from data_engineering.feature_store.feature_definitions import ALL_ENTITIES

        assert len(ALL_ENTITIES) == 1
        assert ALL_ENTITIES[0].name == "subject"


class TestFeatureViews:
    """Tests for Feast feature view definitions."""

    def test_all_feature_views_count(self) -> None:
        from data_engineering.feature_store.feature_definitions import ALL_FEATURE_VIEWS

        assert len(ALL_FEATURE_VIEWS) == 5

    def test_all_feature_views_are_feature_view_instances(self) -> None:
        from data_engineering.feature_store.feature_definitions import ALL_FEATURE_VIEWS

        for fv in ALL_FEATURE_VIEWS:
            assert isinstance(fv, FeatureView)

    def test_total_features_count_is_31(self) -> None:
        from data_engineering.feature_store.feature_definitions import ALL_FEATURE_VIEWS

        total = sum(len(fv.schema) for fv in ALL_FEATURE_VIEWS)
        assert total == 31

    def test_transaction_features_view_has_8_features(self) -> None:
        from data_engineering.feature_store.feature_definitions import (
            transaction_features_view,
        )

        assert len(transaction_features_view.schema) == 8
        assert transaction_features_view.name == "transaction_features"

    def test_network_features_view_has_6_features(self) -> None:
        from data_engineering.feature_store.feature_definitions import (
            network_features_view,
        )

        assert len(network_features_view.schema) == 6

    def test_supply_chain_features_view_has_6_features(self) -> None:
        from data_engineering.feature_store.feature_definitions import (
            supply_chain_features_view,
        )

        assert len(supply_chain_features_view.schema) == 6

    def test_compliance_features_view_has_5_features(self) -> None:
        from data_engineering.feature_store.feature_definitions import (
            compliance_features_view,
        )

        assert len(compliance_features_view.schema) == 5

    def test_core_features_view_has_6_features(self) -> None:
        from data_engineering.feature_store.feature_definitions import (
            core_features_view,
        )

        assert len(core_features_view.schema) == 6

    def test_all_views_are_online(self) -> None:
        from data_engineering.feature_store.feature_definitions import ALL_FEATURE_VIEWS

        for fv in ALL_FEATURE_VIEWS:
            assert fv.online is True

    def test_all_views_have_24h_ttl(self) -> None:
        from datetime import timedelta

        from data_engineering.feature_store.feature_definitions import ALL_FEATURE_VIEWS

        for fv in ALL_FEATURE_VIEWS:
            assert fv.ttl == timedelta(hours=24)

    def test_feature_names_match_specification(self) -> None:
        from data_engineering.feature_store.feature_definitions import ALL_FEATURE_VIEWS

        expected_names = {
            "tx_volume_30d", "tx_value_30d", "tx_volume_volatility",
            "incoming_outgoing_ratio", "avg_transaction_size",
            "max_single_transaction", "days_since_last_tx",
            "unique_counterparties_30d",
            "network_degree", "network_clustering", "network_betweenness",
            "reciprocal_relationships", "merchant_diversity",
            "high_activity_neighbors",
            "supplier_payment_punctuality", "invoice_collection_days",
            "supply_chain_depth", "customer_concentration",
            "supplier_diversification", "days_payable_outstanding",
            "kyc_verification_days", "aml_risk_score",
            "identity_match_confidence", "sanctions_list_flag", "pep_flag",
            "cblri", "utdi", "scfv", "ddc_ratio", "niq_score", "gos_index",
        }
        actual_names = set()
        for fv in ALL_FEATURE_VIEWS:
            for f in fv.schema:
                actual_names.add(f.name)

        assert actual_names == expected_names
