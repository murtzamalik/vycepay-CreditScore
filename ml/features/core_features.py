"""Six Core Features — The VyceScore Scoring Moat (BRD 11.3.5).

Wraps the existing feature definitions in ``ml.features.definitions``
with the standardised BaseFeatureComputer interface, adding data quality
tracking and configurable parameters.

Core features:
1. CBLRI  — Cross-Border Liquidity Resilience Index
2. UTDI   — Utility-Based Transactional Diversity Index
3. SCFV   — Supply Chain Formalization Velocity
4. DDC    — Digital Documentation Compliance Ratio
5. NIQ    — Network Interdependence and Quality Score
6. GOS    — Geographic Operational Stability Index
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ml.features.base import (
    BaseFeatureComputer,
    FeatureCategory,
    FeatureMetadata,
    FeatureResult,
)
from ml.features.definitions import (
    cblri,
    ddc_ratio,
    gos_index,
    niq_score,
    scfv,
    utdi,
)


class CBLRIComputer(BaseFeatureComputer):
    """Cross-Border Liquidity Resilience Index.

    Measures consistency and stability of international cash flows.
    Range: 0.0 - 1.0.
    """

    @property
    def metadata(self) -> FeatureMetadata:
        return FeatureMetadata(
            name="cblri",
            description="Cross-Border Liquidity Resilience Index",
            category=FeatureCategory.CORE,
            value_range=(0.0, 1.0),
            unit="index",
            required_columns=(
                "cross_border_volume_q1",
                "cross_border_volume_q2",
                "cross_border_volume_q3",
                "cross_border_volume_q4",
                "cross_border_tx_count_q1",
                "cross_border_tx_count_q2",
                "cross_border_tx_count_q3",
                "cross_border_tx_count_q4",
                "unique_corridors",
            ),
            default_time_window_days=365,
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
        values = cblri.compute(df)

        return FeatureResult(
            values=values,
            data_quality_score=quality,
            metadata=self.metadata,
        )


class UTDIComputer(BaseFeatureComputer):
    """Utility-Based Transactional Diversity Index.

    Measures merchant category diversity per quarter.
    Range: 0.0 - 1.0.
    """

    @property
    def metadata(self) -> FeatureMetadata:
        return FeatureMetadata(
            name="utdi",
            description="Utility-Based Transactional Diversity Index",
            category=FeatureCategory.CORE,
            value_range=(0.0, 1.0),
            unit="index",
            required_columns=(
                "merchant_categories_q1",
                "merchant_categories_q2",
                "merchant_categories_q3",
                "merchant_categories_q4",
                "total_merchant_categories",
            ),
            default_time_window_days=365,
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
        values = utdi.compute(df)

        return FeatureResult(
            values=values,
            data_quality_score=quality,
            metadata=self.metadata,
        )


class SCFVComputer(BaseFeatureComputer):
    """Supply Chain Formalization Velocity.

    Measures growth in digitized supplier-buyer links via VyceTrade.
    Range: 0.0 - 1.0.
    """

    @property
    def metadata(self) -> FeatureMetadata:
        return FeatureMetadata(
            name="scfv",
            description="Supply Chain Formalization Velocity",
            category=FeatureCategory.CORE,
            value_range=(0.0, 1.0),
            unit="index",
            required_columns=(
                "digitized_links_current",
                "digitized_links_6m_ago",
                "total_trade_relationships",
                "invoices_digitized_pct",
            ),
            default_time_window_days=180,
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
        values = scfv.compute(df)

        return FeatureResult(
            values=values,
            data_quality_score=quality,
            metadata=self.metadata,
        )


class DDCRatioComputer(BaseFeatureComputer):
    """Digital Documentation Compliance Ratio.

    Measures operational task completion rate.
    Range: 0.0 - 1.0.
    """

    @property
    def metadata(self) -> FeatureMetadata:
        return FeatureMetadata(
            name="ddc_ratio",
            description="Digital Documentation Compliance Ratio",
            category=FeatureCategory.CORE,
            value_range=(0.0, 1.0),
            unit="ratio",
            required_columns=(
                "tasks_completed",
                "tasks_assigned",
                "avg_completion_days",
                "tasks_overdue",
            ),
            default_time_window_days=365,
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
        values = ddc_ratio.compute(df)

        return FeatureResult(
            values=values,
            data_quality_score=quality,
            metadata=self.metadata,
        )


class NIQScoreComputer(BaseFeatureComputer):
    """Network Interdependence and Quality Score.

    Average VyceScore of top 5 trading partners.
    Range: 0 - 100.
    """

    @property
    def metadata(self) -> FeatureMetadata:
        return FeatureMetadata(
            name="niq_score",
            description="Network Interdependence and Quality Score",
            category=FeatureCategory.CORE,
            value_range=(0.0, 100.0),
            unit="score",
            required_columns=(
                "partner_score_1",
                "partner_score_2",
                "partner_score_3",
                "partner_score_4",
                "partner_score_5",
            ),
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
        values = niq_score.compute(df)

        return FeatureResult(
            values=values,
            data_quality_score=quality,
            metadata=self.metadata,
        )


class GOSIndexComputer(BaseFeatureComputer):
    """Geographic Operational Stability Index.

    Measures GPS variance of transaction endpoints.
    Range: 0.0 - 1.0 (higher = more stable).
    """

    @property
    def metadata(self) -> FeatureMetadata:
        return FeatureMetadata(
            name="gos_index",
            description="Geographic Operational Stability Index",
            category=FeatureCategory.CORE,
            value_range=(0.0, 1.0),
            unit="index",
            required_columns=(
                "gps_variance_km",
                "primary_location_tx_pct",
                "unique_transaction_locations",
            ),
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
        values = gos_index.compute(df)

        return FeatureResult(
            values=values,
            data_quality_score=quality,
            metadata=self.metadata,
        )


# Convenience: all core feature computers
ALL_CORE_FEATURES: list[type[BaseFeatureComputer]] = [
    CBLRIComputer,
    UTDIComputer,
    SCFVComputer,
    DDCRatioComputer,
    NIQScoreComputer,
    GOSIndexComputer,
]
