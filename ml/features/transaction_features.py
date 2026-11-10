"""Transaction Features (BRD 11.3.1).

Computes features derived from an entity's transaction history:
volume, value, volatility, directionality, counterparty diversity, and recency.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from ml.features.base import (
    BaseFeatureComputer,
    FeatureCategory,
    FeatureMetadata,
    FeatureResult,
)


class TxVolume30d(BaseFeatureComputer):
    """Number of transactions in the last N days."""

    @property
    def metadata(self) -> FeatureMetadata:
        return FeatureMetadata(
            name="tx_volume_30d",
            description="Number of transactions in last 30 days",
            category=FeatureCategory.TRANSACTION,
            value_range=(0, None),
            unit="count",
            required_columns=("transaction_date",),
            default_time_window_days=30,
        )

    def compute(
        self,
        df: pd.DataFrame,
        *,
        time_window_days: int | None = None,
    ) -> FeatureResult:
        window = time_window_days or self.metadata.default_time_window_days
        required = list(self.metadata.required_columns)
        missing = self._validate_columns(df, required)
        if missing:
            return self._empty_result(df, fill=np.nan)

        quality = self._compute_data_quality(df, required)
        dates = pd.to_datetime(df["transaction_date"], errors="coerce")
        cutoff = pd.Timestamp.now(tz=None) - pd.Timedelta(days=window)
        in_window = (dates >= cutoff).astype(float)
        in_window = in_window.where(dates.notna(), other=np.nan)

        # When df has one row per transaction, group by entity_id if present
        if "entity_id" in df.columns:
            mask = dates >= cutoff
            counts = df.loc[mask.fillna(False)].groupby("entity_id").size()
            values = counts.reindex(df["entity_id"].unique(), fill_value=0)
            result_series = pd.Series(
                values.values, index=values.index, name=self.metadata.name
            )
        else:
            # Pre-aggregated: expect tx_count_in_window column
            if "tx_count_in_window" in df.columns:
                result_series = df["tx_count_in_window"].astype(float).rename(self.metadata.name)
            else:
                result_series = in_window.rename(self.metadata.name)

        return FeatureResult(
            values=result_series,
            data_quality_score=quality,
            metadata=self.metadata,
        )


class TxValue30d(BaseFeatureComputer):
    """Total transaction value in the last N days."""

    @property
    def metadata(self) -> FeatureMetadata:
        return FeatureMetadata(
            name="tx_value_30d",
            description="Total transaction value in last 30 days (KES)",
            category=FeatureCategory.TRANSACTION,
            value_range=(0, None),
            unit="KES",
            required_columns=("tx_total_value",),
            default_time_window_days=30,
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
        values = df["tx_total_value"].astype(float).clip(lower=0)
        result_series = values.rename(self.metadata.name)

        return FeatureResult(
            values=result_series,
            data_quality_score=quality,
            metadata=self.metadata,
        )


class TxVolumeVolatility(BaseFeatureComputer):
    """Coefficient of variation in monthly transaction volume.

    Computed over the last 6 months of monthly volume counts.
    High volatility indicates irregular transaction behaviour.
    """

    @property
    def metadata(self) -> FeatureMetadata:
        return FeatureMetadata(
            name="tx_volume_volatility",
            description="Coefficient of variation in monthly transaction volume",
            category=FeatureCategory.TRANSACTION,
            value_range=(0, None),
            unit="ratio",
            required_columns=(
                "tx_count_m1",
                "tx_count_m2",
                "tx_count_m3",
                "tx_count_m4",
                "tx_count_m5",
                "tx_count_m6",
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
        monthly = df[list(required)].values.astype(float)
        cv = self._coefficient_of_variation(monthly)

        return FeatureResult(
            values=pd.Series(cv, index=df.index, name=self.metadata.name),
            data_quality_score=quality,
            metadata=self.metadata,
        )


class IncomingOutgoingRatio(BaseFeatureComputer):
    """Ratio of incoming to outgoing transactions.

    Values > 1 indicate net receiver; < 1 indicate net sender.
    """

    @property
    def metadata(self) -> FeatureMetadata:
        return FeatureMetadata(
            name="incoming_outgoing_ratio",
            description="Ratio of incoming to outgoing transactions",
            category=FeatureCategory.TRANSACTION,
            value_range=(0, None),
            unit="ratio",
            required_columns=("incoming_tx_count", "outgoing_tx_count"),
            default_time_window_days=30,
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
        incoming = df["incoming_tx_count"].values.astype(float)
        outgoing = df["outgoing_tx_count"].values.astype(float)
        ratio = self._safe_divide(incoming, outgoing, fill=np.nan)

        return FeatureResult(
            values=pd.Series(ratio, index=df.index, name=self.metadata.name),
            data_quality_score=quality,
            metadata=self.metadata,
        )


class AvgTransactionSize(BaseFeatureComputer):
    """Average value per transaction."""

    @property
    def metadata(self) -> FeatureMetadata:
        return FeatureMetadata(
            name="avg_transaction_size",
            description="Average value per transaction (KES)",
            category=FeatureCategory.TRANSACTION,
            value_range=(0, None),
            unit="KES",
            required_columns=("tx_total_value", "tx_total_count"),
            default_time_window_days=30,
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
        total_value = df["tx_total_value"].values.astype(float)
        total_count = df["tx_total_count"].values.astype(float)
        avg = self._safe_divide(total_value, total_count, fill=np.nan)

        return FeatureResult(
            values=pd.Series(avg, index=df.index, name=self.metadata.name),
            data_quality_score=quality,
            metadata=self.metadata,
        )


class MaxSingleTransaction(BaseFeatureComputer):
    """Largest transaction value in the observation window."""

    @property
    def metadata(self) -> FeatureMetadata:
        return FeatureMetadata(
            name="max_single_transaction",
            description="Largest single transaction value (KES)",
            category=FeatureCategory.TRANSACTION,
            value_range=(0, None),
            unit="KES",
            required_columns=("max_tx_value",),
            default_time_window_days=30,
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
        values = df["max_tx_value"].astype(float).clip(lower=0)

        return FeatureResult(
            values=values.rename(self.metadata.name),
            data_quality_score=quality,
            metadata=self.metadata,
        )


class DaysSinceLastTx(BaseFeatureComputer):
    """Days since the most recent transaction."""

    @property
    def metadata(self) -> FeatureMetadata:
        return FeatureMetadata(
            name="days_since_last_tx",
            description="Days since most recent transaction",
            category=FeatureCategory.TRANSACTION,
            value_range=(0, None),
            unit="days",
            required_columns=("last_transaction_date",),
            default_time_window_days=30,
        )

    def compute(
        self,
        df: pd.DataFrame,
        *,
        time_window_days: int | None = None,
        reference_date: datetime | None = None,
    ) -> FeatureResult:
        required = list(self.metadata.required_columns)
        missing = self._validate_columns(df, required)
        if missing:
            return self._empty_result(df, fill=np.nan)

        quality = self._compute_data_quality(df, required)
        last_dates = pd.to_datetime(df["last_transaction_date"], errors="coerce")
        ref = pd.Timestamp(reference_date) if reference_date else pd.Timestamp.now()
        days = (ref - last_dates).dt.days.astype(float)
        # Negative values (future dates) become NaN
        days = days.where(days >= 0, other=np.nan)

        return FeatureResult(
            values=days.rename(self.metadata.name),
            data_quality_score=quality,
            metadata=self.metadata,
        )


class UniqueCounterparties30d(BaseFeatureComputer):
    """Number of unique transaction partners in the last N days."""

    @property
    def metadata(self) -> FeatureMetadata:
        return FeatureMetadata(
            name="unique_counterparties_30d",
            description="Number of unique transaction partners in last 30 days",
            category=FeatureCategory.TRANSACTION,
            value_range=(0, None),
            unit="count",
            required_columns=("unique_counterparties",),
            default_time_window_days=30,
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
        values = df["unique_counterparties"].astype(float).clip(lower=0)

        return FeatureResult(
            values=values.rename(self.metadata.name),
            data_quality_score=quality,
            metadata=self.metadata,
        )


# Convenience: all transaction feature computers
ALL_TRANSACTION_FEATURES: list[type[BaseFeatureComputer]] = [
    TxVolume30d,
    TxValue30d,
    TxVolumeVolatility,
    IncomingOutgoingRatio,
    AvgTransactionSize,
    MaxSingleTransaction,
    DaysSinceLastTx,
    UniqueCounterparties30d,
]
