"""Base classes and protocols for VyceScore feature computation.

All feature computation modules should implement the FeatureComputer protocol
or subclass BaseFeatureComputer for standardized feature engineering.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable

import numpy as np
import pandas as pd


class FeatureCategory(str, Enum):
    """Categories for grouping related features."""

    TRANSACTION = "transaction"
    NETWORK = "network"
    SUPPLY_CHAIN = "supply_chain"
    COMPLIANCE = "compliance"
    CORE = "core"


@dataclass(frozen=True)
class FeatureMetadata:
    """Metadata describing a single feature."""

    name: str
    description: str
    category: FeatureCategory
    value_range: tuple[float | None, float | None] = (None, None)
    unit: str = ""
    required_columns: tuple[str, ...] = ()
    default_time_window_days: int = 30


@dataclass
class FeatureResult:
    """Result of a feature computation including data quality information."""

    values: pd.Series
    data_quality_score: float  # 0.0 - 1.0
    metadata: FeatureMetadata
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.data_quality_score = float(np.clip(self.data_quality_score, 0.0, 1.0))


@runtime_checkable
class FeatureComputer(Protocol):
    """Protocol that all feature computation classes must follow."""

    @property
    def metadata(self) -> FeatureMetadata:
        """Return metadata about this feature."""
        ...

    def compute(
        self,
        df: pd.DataFrame,
        *,
        time_window_days: int | None = None,
    ) -> FeatureResult:
        """Compute the feature values from input data.

        Args:
            df: Input DataFrame containing the raw data.
            time_window_days: Override default time window for computation.

        Returns:
            FeatureResult with computed values and quality information.
        """
        ...


class BaseFeatureComputer(abc.ABC):
    """Abstract base class for feature computers with shared utilities."""

    @property
    @abc.abstractmethod
    def metadata(self) -> FeatureMetadata:
        """Return metadata about this feature."""

    @abc.abstractmethod
    def compute(
        self,
        df: pd.DataFrame,
        *,
        time_window_days: int | None = None,
    ) -> FeatureResult:
        """Compute the feature values from input data."""

    def _validate_columns(
        self,
        df: pd.DataFrame,
        required: tuple[str, ...] | list[str],
    ) -> list[str]:
        """Check which required columns are present.

        Returns:
            List of missing column names (empty if all present).
        """
        return [col for col in required if col not in df.columns]

    def _compute_data_quality(
        self,
        df: pd.DataFrame,
        required_columns: tuple[str, ...] | list[str],
    ) -> float:
        """Compute data quality score based on input completeness.

        Quality is the fraction of non-null values across required columns
        that are actually present in the DataFrame.

        Returns:
            Float in [0.0, 1.0] where 1.0 means all data is present.
        """
        if not required_columns or len(df) == 0:
            return 0.0

        present_cols = [c for c in required_columns if c in df.columns]
        if not present_cols:
            return 0.0

        # Fraction of required columns that exist
        col_presence = len(present_cols) / len(required_columns)

        # Among existing columns, fraction of non-null values
        if present_cols:
            total_cells = len(df) * len(present_cols)
            non_null_cells = df[present_cols].notna().sum().sum()
            value_completeness = float(non_null_cells / total_cells) if total_cells > 0 else 0.0
        else:
            value_completeness = 0.0

        # Combined quality: geometric mean of column presence and value completeness
        return float(np.sqrt(col_presence * value_completeness))

    def _safe_divide(
        self,
        numerator: np.ndarray,
        denominator: np.ndarray,
        fill: float = 0.0,
    ) -> np.ndarray:
        """Divide arrays safely, replacing division-by-zero with fill value."""
        with np.errstate(divide="ignore", invalid="ignore"):
            result = np.where(denominator != 0, numerator / denominator, fill)
        return result

    def _coefficient_of_variation(self, values: np.ndarray) -> np.ndarray:
        """Compute coefficient of variation along axis=1 (row-wise).

        Returns NaN for rows with zero mean.
        """
        means = np.nanmean(values, axis=1)
        stds = np.nanstd(values, axis=1)
        return self._safe_divide(stds, means, fill=np.nan)

    def _empty_result(self, df: pd.DataFrame, fill: float = np.nan) -> FeatureResult:
        """Create a result filled with a constant value (for error cases)."""
        return FeatureResult(
            values=pd.Series(fill, index=df.index, name=self.metadata.name),
            data_quality_score=0.0,
            metadata=self.metadata,
            diagnostics={"error": "missing_required_columns"},
        )
