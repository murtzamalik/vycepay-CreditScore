"""Network Features (BRD 11.3.2).

Computes features derived from the entity's position and behaviour
within its transaction network graph using networkx for graph metrics.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

try:
    import networkx as nx
except ImportError:  # pragma: no cover
    nx = None  # type: ignore[assignment]

from ml.features.base import (
    BaseFeatureComputer,
    FeatureCategory,
    FeatureMetadata,
    FeatureResult,
)


def _ensure_networkx() -> None:
    """Raise ImportError if networkx is not available."""
    if nx is None:
        raise ImportError(
            "networkx is required for network features. "
            "Install it with: pip install networkx"
        )


class NetworkDegree(BaseFeatureComputer):
    """Number of direct connections (transaction partners) per entity."""

    @property
    def metadata(self) -> FeatureMetadata:
        return FeatureMetadata(
            name="network_degree",
            description="Number of direct connections in transaction network",
            category=FeatureCategory.NETWORK,
            value_range=(0, None),
            unit="count",
            required_columns=("entity_id", "counterparty_id"),
        )

    def compute(
        self,
        df: pd.DataFrame,
        *,
        time_window_days: int | None = None,
    ) -> FeatureResult:
        required = list(self.metadata.required_columns)
        missing = self._validate_columns(df, required)
        if missing:
            return self._empty_result(df, fill=np.nan)

        _ensure_networkx()
        quality = self._compute_data_quality(df, required)

        G = nx.from_pandas_edgelist(
            df, source="entity_id", target="counterparty_id"
        )
        degree_dict = dict(G.degree())
        entities = df["entity_id"].unique()
        degrees = pd.Series(
            [degree_dict.get(e, 0) for e in entities],
            index=entities,
            name=self.metadata.name,
            dtype=float,
        )

        return FeatureResult(
            values=degrees,
            data_quality_score=quality,
            metadata=self.metadata,
        )


class NetworkClustering(BaseFeatureComputer):
    """Clustering coefficient of local network.

    Measures how interconnected an entity's neighbours are with each other.
    High clustering suggests a tightly-knit trading community.
    """

    @property
    def metadata(self) -> FeatureMetadata:
        return FeatureMetadata(
            name="network_clustering",
            description="Clustering coefficient of local network",
            category=FeatureCategory.NETWORK,
            value_range=(0.0, 1.0),
            unit="ratio",
            required_columns=("entity_id", "counterparty_id"),
        )

    def compute(
        self,
        df: pd.DataFrame,
        *,
        time_window_days: int | None = None,
    ) -> FeatureResult:
        required = list(self.metadata.required_columns)
        missing = self._validate_columns(df, required)
        if missing:
            return self._empty_result(df, fill=np.nan)

        _ensure_networkx()
        quality = self._compute_data_quality(df, required)

        G = nx.from_pandas_edgelist(
            df, source="entity_id", target="counterparty_id"
        )
        clustering_dict = nx.clustering(G)
        entities = df["entity_id"].unique()
        clustering = pd.Series(
            [clustering_dict.get(e, 0.0) for e in entities],
            index=entities,
            name=self.metadata.name,
            dtype=float,
        )

        return FeatureResult(
            values=clustering,
            data_quality_score=quality,
            metadata=self.metadata,
        )


class NetworkBetweenness(BaseFeatureComputer):
    """Betweenness centrality in the transaction network.

    High betweenness indicates the entity acts as a bridge/hub between
    otherwise disconnected parts of the network.
    """

    @property
    def metadata(self) -> FeatureMetadata:
        return FeatureMetadata(
            name="network_betweenness",
            description="Betweenness centrality in transaction network",
            category=FeatureCategory.NETWORK,
            value_range=(0.0, 1.0),
            unit="ratio",
            required_columns=("entity_id", "counterparty_id"),
        )

    def compute(
        self,
        df: pd.DataFrame,
        *,
        time_window_days: int | None = None,
    ) -> FeatureResult:
        required = list(self.metadata.required_columns)
        missing = self._validate_columns(df, required)
        if missing:
            return self._empty_result(df, fill=np.nan)

        _ensure_networkx()
        quality = self._compute_data_quality(df, required)

        G = nx.from_pandas_edgelist(
            df, source="entity_id", target="counterparty_id"
        )
        betweenness_dict = nx.betweenness_centrality(G)
        entities = df["entity_id"].unique()
        betweenness = pd.Series(
            [betweenness_dict.get(e, 0.0) for e in entities],
            index=entities,
            name=self.metadata.name,
            dtype=float,
        )

        return FeatureResult(
            values=betweenness,
            data_quality_score=quality,
            metadata=self.metadata,
        )


class ReciprocalRelationships(BaseFeatureComputer):
    """Count of two-way transaction relationships.

    A reciprocal relationship exists when entity A sends transactions
    to entity B AND entity B sends transactions to entity A.
    """

    @property
    def metadata(self) -> FeatureMetadata:
        return FeatureMetadata(
            name="reciprocal_relationships",
            description="Count of two-way transaction relationships",
            category=FeatureCategory.NETWORK,
            value_range=(0, None),
            unit="count",
            required_columns=("entity_id", "counterparty_id", "direction"),
        )

    def compute(
        self,
        df: pd.DataFrame,
        *,
        time_window_days: int | None = None,
    ) -> FeatureResult:
        required = list(self.metadata.required_columns)
        missing = self._validate_columns(df, required)
        if missing:
            return self._empty_result(df, fill=np.nan)

        quality = self._compute_data_quality(df, required)

        # Build directed edge set
        outgoing = df[df["direction"] == "outgoing"][
            ["entity_id", "counterparty_id"]
        ].drop_duplicates()
        incoming = df[df["direction"] == "incoming"][
            ["entity_id", "counterparty_id"]
        ].drop_duplicates()

        # For each entity, find counterparties that appear in both directions
        entities = df["entity_id"].unique()
        reciprocal_counts: dict[str, int] = {}

        out_set: dict[str, set[str]] = {}
        for _, row in outgoing.iterrows():
            eid = row["entity_id"]
            cid = row["counterparty_id"]
            out_set.setdefault(eid, set()).add(cid)

        in_set: dict[str, set[str]] = {}
        for _, row in incoming.iterrows():
            eid = row["entity_id"]
            cid = row["counterparty_id"]
            in_set.setdefault(eid, set()).add(cid)

        for e in entities:
            sent_to = out_set.get(e, set())
            received_from = in_set.get(e, set())
            reciprocal_counts[e] = len(sent_to & received_from)

        values = pd.Series(reciprocal_counts, name=self.metadata.name, dtype=float)
        values = values.reindex(entities, fill_value=0)

        return FeatureResult(
            values=values,
            data_quality_score=quality,
            metadata=self.metadata,
        )


class MerchantDiversity(BaseFeatureComputer):
    """Shannon diversity index of merchant categories.

    Higher diversity indicates the entity transacts across many different
    merchant types, suggesting a more robust operational profile.
    """

    @property
    def metadata(self) -> FeatureMetadata:
        return FeatureMetadata(
            name="merchant_diversity",
            description="Shannon diversity of merchant categories",
            category=FeatureCategory.NETWORK,
            value_range=(0, None),
            unit="nats",
            required_columns=("entity_id", "merchant_category"),
        )

    def compute(
        self,
        df: pd.DataFrame,
        *,
        time_window_days: int | None = None,
    ) -> FeatureResult:
        required = list(self.metadata.required_columns)
        missing = self._validate_columns(df, required)
        if missing:
            return self._empty_result(df, fill=np.nan)

        quality = self._compute_data_quality(df, required)

        def _shannon_diversity(group: pd.DataFrame) -> float:
            counts = group["merchant_category"].value_counts()
            total = counts.sum()
            if total == 0:
                return 0.0
            proportions = counts / total
            # Shannon entropy: -sum(p * ln(p))
            return float(-np.sum(proportions * np.log(proportions)))

        entities = df["entity_id"].unique()
        diversity = df.groupby("entity_id").apply(
            _shannon_diversity, include_groups=False
        )
        diversity = diversity.reindex(entities, fill_value=0.0)
        diversity.name = self.metadata.name

        return FeatureResult(
            values=diversity.astype(float),
            data_quality_score=quality,
            metadata=self.metadata,
        )


class HighActivityNeighbors(BaseFeatureComputer):
    """Count of neighbors with high transaction volume.

    A neighbor is considered high-activity if their transaction count
    exceeds the threshold (default: median of the network).
    """

    HIGH_ACTIVITY_THRESHOLD: float = 50.0  # Default: 50 transactions

    @property
    def metadata(self) -> FeatureMetadata:
        return FeatureMetadata(
            name="high_activity_neighbors",
            description="Count of neighbors with high transaction volume",
            category=FeatureCategory.NETWORK,
            value_range=(0, None),
            unit="count",
            required_columns=(
                "entity_id",
                "counterparty_id",
                "counterparty_tx_count",
            ),
        )

    def compute(
        self,
        df: pd.DataFrame,
        *,
        time_window_days: int | None = None,
        activity_threshold: float | None = None,
    ) -> FeatureResult:
        required = list(self.metadata.required_columns)
        missing = self._validate_columns(df, required)
        if missing:
            return self._empty_result(df, fill=np.nan)

        quality = self._compute_data_quality(df, required)
        threshold = activity_threshold or self.HIGH_ACTIVITY_THRESHOLD

        high_activity = df[df["counterparty_tx_count"] >= threshold]
        counts = (
            high_activity.groupby("entity_id")["counterparty_id"]
            .nunique()
        )
        entities = df["entity_id"].unique()
        counts = counts.reindex(entities, fill_value=0)
        counts.name = self.metadata.name

        return FeatureResult(
            values=counts.astype(float),
            data_quality_score=quality,
            metadata=self.metadata,
        )


# Convenience: all network feature computers
ALL_NETWORK_FEATURES: list[type[BaseFeatureComputer]] = [
    NetworkDegree,
    NetworkClustering,
    NetworkBetweenness,
    ReciprocalRelationships,
    MerchantDiversity,
    HighActivityNeighbors,
]
