"""Supply Chain Features (BRD 11.3.3).

Computes features derived from VyceTrade supplier/buyer relationships,
invoice management, and supply chain structure.
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


class SupplierPaymentPunctuality(BaseFeatureComputer):
    """Percentage of on-time supplier payments.

    Measures operational discipline: entities that pay suppliers on time
    are more likely to maintain stable supply chains and meet their own
    credit obligations.
    """

    @property
    def metadata(self) -> FeatureMetadata:
        return FeatureMetadata(
            name="supplier_payment_punctuality",
            description="Percentage of on-time supplier payments",
            category=FeatureCategory.SUPPLY_CHAIN,
            value_range=(0.0, 1.0),
            unit="ratio",
            required_columns=("on_time_payments", "total_supplier_payments"),
            default_time_window_days=90,
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
        on_time = df["on_time_payments"].values.astype(float)
        total = df["total_supplier_payments"].values.astype(float)
        ratio = self._safe_divide(on_time, total, fill=np.nan)
        ratio = np.clip(ratio, 0.0, 1.0)

        return FeatureResult(
            values=pd.Series(ratio, index=df.index, name=self.metadata.name),
            data_quality_score=quality,
            metadata=self.metadata,
        )


class InvoiceCollectionDays(BaseFeatureComputer):
    """Average days to collect invoice payments from customers.

    Lower values indicate stronger cash collection capability.
    """

    @property
    def metadata(self) -> FeatureMetadata:
        return FeatureMetadata(
            name="invoice_collection_days",
            description="Average days to collect invoice payments",
            category=FeatureCategory.SUPPLY_CHAIN,
            value_range=(0, None),
            unit="days",
            required_columns=("avg_collection_days",),
            default_time_window_days=90,
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
        values = df["avg_collection_days"].astype(float).clip(lower=0)

        return FeatureResult(
            values=values.rename(self.metadata.name),
            data_quality_score=quality,
            metadata=self.metadata,
        )


class SupplyChainDepth(BaseFeatureComputer):
    """Number of tiers in the entity's supply chain.

    Deeper supply chains indicate more complex operations and may
    signal either maturity (positive) or fragility (negative depending
    on concentration). Measured as the longest path from raw supplier
    to end customer in the entity's trade network.
    """

    @property
    def metadata(self) -> FeatureMetadata:
        return FeatureMetadata(
            name="supply_chain_depth",
            description="Number of tiers in supply chain",
            category=FeatureCategory.SUPPLY_CHAIN,
            value_range=(0, None),
            unit="tiers",
            required_columns=("supply_chain_tiers",),
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
        values = df["supply_chain_tiers"].astype(float).clip(lower=0)

        return FeatureResult(
            values=values.rename(self.metadata.name),
            data_quality_score=quality,
            metadata=self.metadata,
        )


class CustomerConcentration(BaseFeatureComputer):
    """Revenue concentration across customers measured by HHI.

    Herfindahl-Hirschman Index (HHI): sum of squared revenue shares.
    Range: 0 (perfectly diversified) to 1 (single customer).
    High concentration = high risk if that customer defaults.
    """

    @property
    def metadata(self) -> FeatureMetadata:
        return FeatureMetadata(
            name="customer_concentration",
            description="Revenue concentration across customers (HHI)",
            category=FeatureCategory.SUPPLY_CHAIN,
            value_range=(0.0, 1.0),
            unit="HHI",
            required_columns=("entity_id", "customer_id", "revenue"),
        )

    def compute(
        self,
        df: pd.DataFrame,
        *,
        time_window_days: int | None = None,
    ) -> FeatureResult:
        required = list(self.metadata.required_columns)
        missing = self._validate_columns(df, required)

        # Also support pre-aggregated HHI column
        if missing and "customer_concentration_hhi" in df.columns:
            quality = self._compute_data_quality(df, ["customer_concentration_hhi"])
            values = df["customer_concentration_hhi"].astype(float).clip(0.0, 1.0)
            return FeatureResult(
                values=values.rename(self.metadata.name),
                data_quality_score=quality,
                metadata=self.metadata,
            )

        if missing:
            return self._empty_result(df, fill=np.nan)

        quality = self._compute_data_quality(df, required)

        def _hhi(group: pd.DataFrame) -> float:
            revenues = group["revenue"].astype(float)
            total = revenues.sum()
            if total <= 0:
                return np.nan
            shares = revenues / total
            return float((shares ** 2).sum())

        entities = df["entity_id"].unique()
        hhi = df.groupby("entity_id").apply(_hhi, include_groups=False)
        hhi = hhi.reindex(entities, fill_value=np.nan)
        hhi.name = self.metadata.name

        return FeatureResult(
            values=hhi.astype(float),
            data_quality_score=quality,
            metadata=self.metadata,
        )


class SupplierDiversification(BaseFeatureComputer):
    """Number of active suppliers.

    More suppliers generally indicates lower supply-side risk.
    """

    @property
    def metadata(self) -> FeatureMetadata:
        return FeatureMetadata(
            name="supplier_diversification",
            description="Number of active suppliers",
            category=FeatureCategory.SUPPLY_CHAIN,
            value_range=(0, None),
            unit="count",
            required_columns=("active_supplier_count",),
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
        values = df["active_supplier_count"].astype(float).clip(lower=0)

        return FeatureResult(
            values=values.rename(self.metadata.name),
            data_quality_score=quality,
            metadata=self.metadata,
        )


class DaysPayableOutstanding(BaseFeatureComputer):
    """Average days to pay suppliers (DPO).

    Lower DPO indicates faster payment to suppliers. Very high DPO
    may indicate cash flow problems; very low may indicate inefficient
    working capital management.
    """

    @property
    def metadata(self) -> FeatureMetadata:
        return FeatureMetadata(
            name="days_payable_outstanding",
            description="Average days to pay suppliers",
            category=FeatureCategory.SUPPLY_CHAIN,
            value_range=(0, None),
            unit="days",
            required_columns=("avg_days_payable",),
            default_time_window_days=90,
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
        values = df["avg_days_payable"].astype(float).clip(lower=0)

        return FeatureResult(
            values=values.rename(self.metadata.name),
            data_quality_score=quality,
            metadata=self.metadata,
        )


# Convenience: all supply chain feature computers
ALL_SUPPLY_CHAIN_FEATURES: list[type[BaseFeatureComputer]] = [
    SupplierPaymentPunctuality,
    InvoiceCollectionDays,
    SupplyChainDepth,
    CustomerConcentration,
    SupplierDiversification,
    DaysPayableOutstanding,
]
