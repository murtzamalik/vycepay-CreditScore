"""Feast entity and feature view definitions for all 31 VyceScore features.

Organizes features across five categories matching the ml/features/ module:
    1. Transaction Features (8 features)
    2. Network Features (6 features)
    3. Supply Chain Features (6 features)
    4. Compliance Features (5 features)
    5. Core Features (6 features)

All feature views are keyed on the ``subject`` entity (national_id_hash)
and are materialized to the Redis online store for real-time serving.
"""

from __future__ import annotations

from datetime import timedelta

from feast import Entity, FeatureView, Field, FileSource, ValueType
from feast.types import Float64, Int64

# ---------------------------------------------------------------------------
# Entity
# ---------------------------------------------------------------------------

subject = Entity(
    name="subject",
    join_keys=["national_id_hash"],
    value_type=ValueType.STRING,
    description=(
        "VyceScore subject entity (individual or MSME), identified by "
        "SHA-256 hash of national ID. PII is never stored."
    ),
    tags={
        "owner": "vycescore-data-eng",
        "pii": "false",
    },
)

# ---------------------------------------------------------------------------
# Data sources (offline store — Parquet)
# ---------------------------------------------------------------------------

_DATALAKE_BASE = "s3a://vycescore-datalake"

transaction_features_source = FileSource(
    name="transaction_features_source",
    path=f"{_DATALAKE_BASE}/features/transaction/",
    timestamp_field="computed_at",
    created_timestamp_column="computed_at",
    description="Parquet files with computed transaction features, partitioned by dt.",
    tags={"format": "parquet", "partitioned_by": "dt"},
)

network_features_source = FileSource(
    name="network_features_source",
    path=f"{_DATALAKE_BASE}/features/network/",
    timestamp_field="computed_at",
    created_timestamp_column="computed_at",
    description="Parquet files with computed network features.",
    tags={"format": "parquet", "partitioned_by": "dt"},
)

supply_chain_features_source = FileSource(
    name="supply_chain_features_source",
    path=f"{_DATALAKE_BASE}/features/supply_chain/",
    timestamp_field="computed_at",
    created_timestamp_column="computed_at",
    description="Parquet files with computed supply chain features.",
    tags={"format": "parquet", "partitioned_by": "dt"},
)

compliance_features_source = FileSource(
    name="compliance_features_source",
    path=f"{_DATALAKE_BASE}/features/compliance/",
    timestamp_field="computed_at",
    created_timestamp_column="computed_at",
    description="Parquet files with computed compliance features.",
    tags={"format": "parquet", "partitioned_by": "dt"},
)

core_features_source = FileSource(
    name="core_features_source",
    path=f"{_DATALAKE_BASE}/features/core/",
    timestamp_field="computed_at",
    created_timestamp_column="computed_at",
    description="Parquet files with computed core scoring features.",
    tags={"format": "parquet", "partitioned_by": "dt"},
)

# ---------------------------------------------------------------------------
# 1. Transaction Features FeatureView (8 features)
# ---------------------------------------------------------------------------

transaction_features_view = FeatureView(
    name="transaction_features",
    entities=[subject],
    ttl=timedelta(hours=24),
    schema=[
        Field(name="tx_volume_30d", dtype=Float64,
              description="Number of transactions in last 30 days"),
        Field(name="tx_value_30d", dtype=Float64,
              description="Total transaction value in last 30 days (KES)"),
        Field(name="tx_volume_volatility", dtype=Float64,
              description="CV of monthly transaction volume (6 months)"),
        Field(name="incoming_outgoing_ratio", dtype=Float64,
              description="Ratio of incoming to outgoing transactions"),
        Field(name="avg_transaction_size", dtype=Float64,
              description="Average value per transaction (KES)"),
        Field(name="max_single_transaction", dtype=Float64,
              description="Largest single transaction value (KES)"),
        Field(name="days_since_last_tx", dtype=Float64,
              description="Days since most recent transaction"),
        Field(name="unique_counterparties_30d", dtype=Float64,
              description="Unique transaction partners in last 30 days"),
    ],
    source=transaction_features_source,
    online=True,
    tags={
        "owner": "vycescore-data-eng",
        "category": "transaction",
        "version": "v1",
        "refresh": "daily",
    },
    description="Transaction features from VycePay (BRD 11.3.1).",
)

# ---------------------------------------------------------------------------
# 2. Network Features FeatureView (6 features)
# ---------------------------------------------------------------------------

network_features_view = FeatureView(
    name="network_features",
    entities=[subject],
    ttl=timedelta(hours=24),
    schema=[
        Field(name="network_degree", dtype=Float64,
              description="Number of direct connections in transaction network"),
        Field(name="network_clustering", dtype=Float64,
              description="Clustering coefficient of local network [0-1]"),
        Field(name="network_betweenness", dtype=Float64,
              description="Betweenness centrality in transaction network [0-1]"),
        Field(name="reciprocal_relationships", dtype=Float64,
              description="Count of two-way transaction relationships"),
        Field(name="merchant_diversity", dtype=Float64,
              description="Shannon diversity of merchant categories (nats)"),
        Field(name="high_activity_neighbors", dtype=Float64,
              description="Count of neighbors with high transaction volume"),
    ],
    source=network_features_source,
    online=True,
    tags={
        "owner": "vycescore-data-eng",
        "category": "network",
        "version": "v1",
        "refresh": "daily",
    },
    description="Network features from transaction graph (BRD 11.3.2).",
)

# ---------------------------------------------------------------------------
# 3. Supply Chain Features FeatureView (6 features)
# ---------------------------------------------------------------------------

supply_chain_features_view = FeatureView(
    name="supply_chain_features",
    entities=[subject],
    ttl=timedelta(hours=24),
    schema=[
        Field(name="supplier_payment_punctuality", dtype=Float64,
              description="Percentage of on-time supplier payments [0-1]"),
        Field(name="invoice_collection_days", dtype=Float64,
              description="Average days to collect invoice payments"),
        Field(name="supply_chain_depth", dtype=Float64,
              description="Number of tiers in supply chain"),
        Field(name="customer_concentration", dtype=Float64,
              description="Revenue concentration (HHI) [0-1]"),
        Field(name="supplier_diversification", dtype=Float64,
              description="Number of active suppliers"),
        Field(name="days_payable_outstanding", dtype=Float64,
              description="Average days to pay suppliers"),
    ],
    source=supply_chain_features_source,
    online=True,
    tags={
        "owner": "vycescore-data-eng",
        "category": "supply_chain",
        "version": "v1",
        "refresh": "daily",
    },
    description="Supply chain features from VyceTrade (BRD 11.3.3).",
)

# ---------------------------------------------------------------------------
# 4. Compliance Features FeatureView (5 features)
# ---------------------------------------------------------------------------

compliance_features_view = FeatureView(
    name="compliance_features",
    entities=[subject],
    ttl=timedelta(hours=24),
    schema=[
        Field(name="kyc_verification_days", dtype=Float64,
              description="Days since last KYC verification"),
        Field(name="aml_risk_score", dtype=Float64,
              description="AML screening risk rating [0-1]"),
        Field(name="identity_match_confidence", dtype=Float64,
              description="Biometric verification confidence [0-1]"),
        Field(name="sanctions_list_flag", dtype=Float64,
              description="Boolean: entity on sanctions list [0/1]"),
        Field(name="pep_flag", dtype=Float64,
              description="Boolean: politically exposed person [0/1]"),
    ],
    source=compliance_features_source,
    online=True,
    tags={
        "owner": "vycescore-data-eng",
        "category": "compliance",
        "version": "v1",
        "refresh": "daily",
    },
    description="Compliance features from KYC/AML partners (BRD 11.3.4).",
)

# ---------------------------------------------------------------------------
# 5. Core Scoring Features FeatureView (6 features — the scoring moat)
# ---------------------------------------------------------------------------

core_features_view = FeatureView(
    name="core_scoring_features",
    entities=[subject],
    ttl=timedelta(hours=24),
    schema=[
        Field(name="cblri", dtype=Float64,
              description="Cross-Border Liquidity Resilience Index [0-1]"),
        Field(name="utdi", dtype=Float64,
              description="Utility-Based Transactional Diversity Index [0-1]"),
        Field(name="scfv", dtype=Float64,
              description="Supply Chain Formalization Velocity [0-1]"),
        Field(name="ddc_ratio", dtype=Float64,
              description="Digital Documentation Compliance Ratio [0-1]"),
        Field(name="niq_score", dtype=Float64,
              description="Network Interdependence and Quality Score [0-100]"),
        Field(name="gos_index", dtype=Float64,
              description="Geographic Operational Stability Index [0-1]"),
    ],
    source=core_features_source,
    online=True,
    tags={
        "owner": "vycescore-data-eng",
        "category": "core",
        "version": "v1",
        "refresh": "daily",
        "sla": "24h",
    },
    description=(
        "Core scoring features (the VyceScore moat). These 6 features "
        "form the primary input vector for the XGBoost model (BRD 11.3.5)."
    ),
)

# ---------------------------------------------------------------------------
# All feature views for registration
# ---------------------------------------------------------------------------

ALL_FEATURE_VIEWS: list[FeatureView] = [
    transaction_features_view,
    network_features_view,
    supply_chain_features_view,
    compliance_features_view,
    core_features_view,
]

ALL_ENTITIES: list[Entity] = [subject]
