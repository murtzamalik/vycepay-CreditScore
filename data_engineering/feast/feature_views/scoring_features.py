"""
Feast FeatureView definitions for the 6 core VyceScore scoring features.

Feature Views:
    1. scoring_features - All 6 core features for credit scoring inference
    2. transaction_stats - Supporting transaction statistics

These views are materialized to the Redis online store for real-time
serving (Lite/Pro API) and available in the offline store (Parquet)
for batch scoring and model training.

TTL is set to 24 hours to match the daily batch refresh cycle.
"""

from __future__ import annotations

from datetime import timedelta

from feast import FeatureView, Field
from feast.types import Float64, Int64, String

from data_engineering.feast.data_sources.transactions import (
    features_source,
    transaction_stats_source,
)
from data_engineering.feast.entities.customer import customer

# ---------------------------------------------------------------------------
# Core Scoring Features FeatureView
# ---------------------------------------------------------------------------

scoring_features = FeatureView(
    name="scoring_features",
    entities=[customer],
    ttl=timedelta(hours=24),
    schema=[
        Field(
            name="cblri",
            dtype=Float64,
            description="Cross-Border Liquidity Resilience Index [0.0, 1.0]",
            tags={"feature_group": "liquidity"},
        ),
        Field(
            name="utdi",
            dtype=Float64,
            description="Utility-Based Transactional Diversity Index [0.0, 1.0]",
            tags={"feature_group": "diversity"},
        ),
        Field(
            name="scfv",
            dtype=Float64,
            description="Supply Chain Formalization Velocity [0.0, 100.0]",
            tags={"feature_group": "supply_chain"},
        ),
        Field(
            name="ddc_ratio",
            dtype=Float64,
            description="Digital Documentation Compliance Ratio [0.0, 1.0]",
            tags={"feature_group": "compliance"},
        ),
        Field(
            name="niq_score",
            dtype=Float64,
            description="Network Interdependence and Quality Score [300, 900]",
            tags={"feature_group": "network"},
        ),
        Field(
            name="gos_index",
            dtype=Float64,
            description="Geographic Operational Stability Index [0.0, 1.0]",
            tags={"feature_group": "geographic"},
        ),
    ],
    source=features_source,
    online=True,
    tags={
        "owner": "vycescore-data-eng",
        "team": "ml-platform",
        "version": "v1",
        "refresh": "daily",
        "sla": "24h",
    },
    description=(
        "Core scoring features computed daily from VycePay and VyceTrade data. "
        "These 6 features form the input vector for the XGBoost credit scoring model."
    ),
)

# ---------------------------------------------------------------------------
# Transaction Statistics FeatureView (supporting features)
# ---------------------------------------------------------------------------

transaction_stats = FeatureView(
    name="transaction_stats",
    entities=[customer],
    ttl=timedelta(hours=24),
    schema=[
        Field(
            name="total_txn_count_30d",
            dtype=Int64,
            description="Total transactions in the last 30 days",
        ),
        Field(
            name="total_volume_30d",
            dtype=Float64,
            description="Total transaction volume (KES) in the last 30 days",
        ),
        Field(
            name="avg_txn_amount_30d",
            dtype=Float64,
            description="Average transaction amount (KES) in the last 30 days",
        ),
        Field(
            name="distinct_counterparties_30d",
            dtype=Int64,
            description="Distinct counterparties in the last 30 days",
        ),
        Field(
            name="cross_border_ratio_30d",
            dtype=Float64,
            description="Ratio of cross-border transactions in the last 30 days",
        ),
    ],
    source=transaction_stats_source,
    online=True,
    tags={
        "owner": "vycescore-data-eng",
        "team": "ml-platform",
        "version": "v1",
    },
    description=(
        "30-day rolling transaction statistics for each customer. "
        "Used as supplementary features and for monitoring."
    ),
)
