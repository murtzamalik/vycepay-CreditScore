"""Compliance Features (BRD 11.3.4).

Computes features derived from KYC/AML verification status,
identity verification confidence, and regulatory screening results.
These features encode regulatory compliance posture into the scoring model.
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


class KycVerificationDays(BaseFeatureComputer):
    """Days since last KYC verification.

    Fresher KYC data is more reliable. Stale KYC (>365 days) may
    indicate outdated identity information and higher risk.
    """

    @property
    def metadata(self) -> FeatureMetadata:
        return FeatureMetadata(
            name="kyc_verification_days",
            description="Days since last KYC verification",
            category=FeatureCategory.COMPLIANCE,
            value_range=(0, None),
            unit="days",
            required_columns=("kyc_verification_date",),
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
        kyc_dates = pd.to_datetime(df["kyc_verification_date"], errors="coerce")
        ref = pd.Timestamp(reference_date) if reference_date else pd.Timestamp.now()
        days = (ref - kyc_dates).dt.days.astype(float)
        # Negative values (future dates) become NaN
        days = days.where(days >= 0, other=np.nan)

        return FeatureResult(
            values=days.rename(self.metadata.name),
            data_quality_score=quality,
            metadata=self.metadata,
        )


class AmlRiskScore(BaseFeatureComputer):
    """AML screening risk rating, normalized to [0, 1].

    Derived from ComplyAdvantage or equivalent AML screening service.
    0 = lowest risk, 1 = highest risk.
    """

    @property
    def metadata(self) -> FeatureMetadata:
        return FeatureMetadata(
            name="aml_risk_score",
            description="AML screening risk rating (normalized 0-1)",
            category=FeatureCategory.COMPLIANCE,
            value_range=(0.0, 1.0),
            unit="score",
            required_columns=("aml_risk_rating",),
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
        values = df["aml_risk_rating"].astype(float).clip(0.0, 1.0)

        return FeatureResult(
            values=values.rename(self.metadata.name),
            data_quality_score=quality,
            metadata=self.metadata,
        )


class IdentityMatchConfidence(BaseFeatureComputer):
    """Biometric verification confidence score.

    From Smile ID or equivalent identity verification provider.
    Measures how confidently the system matched the person to their
    identity documents. Range: 0.0 (no match) to 1.0 (perfect match).
    """

    @property
    def metadata(self) -> FeatureMetadata:
        return FeatureMetadata(
            name="identity_match_confidence",
            description="Biometric verification confidence (0-1)",
            category=FeatureCategory.COMPLIANCE,
            value_range=(0.0, 1.0),
            unit="score",
            required_columns=("biometric_confidence",),
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
        values = df["biometric_confidence"].astype(float).clip(0.0, 1.0)

        return FeatureResult(
            values=values.rename(self.metadata.name),
            data_quality_score=quality,
            metadata=self.metadata,
        )


class SanctionsListFlag(BaseFeatureComputer):
    """Boolean flag indicating presence on sanctions lists.

    True (1.0) if the entity appears on any sanctions list.
    False (0.0) if clear.
    """

    @property
    def metadata(self) -> FeatureMetadata:
        return FeatureMetadata(
            name="sanctions_list_flag",
            description="Boolean: entity on sanctions list",
            category=FeatureCategory.COMPLIANCE,
            value_range=(0.0, 1.0),
            unit="flag",
            required_columns=("on_sanctions_list",),
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
        # Convert to float boolean: True -> 1.0, False -> 0.0
        raw = df["on_sanctions_list"]
        if raw.dtype == bool or raw.dtype == "boolean":
            values = raw.astype(float)
        else:
            values = raw.astype(float).clip(0.0, 1.0)

        return FeatureResult(
            values=values.rename(self.metadata.name),
            data_quality_score=quality,
            metadata=self.metadata,
        )


class PepFlag(BaseFeatureComputer):
    """Boolean flag for Politically Exposed Person (PEP) status.

    True (1.0) if the entity or its beneficial owners are PEPs.
    False (0.0) otherwise.
    """

    @property
    def metadata(self) -> FeatureMetadata:
        return FeatureMetadata(
            name="pep_flag",
            description="Boolean: politically exposed person",
            category=FeatureCategory.COMPLIANCE,
            value_range=(0.0, 1.0),
            unit="flag",
            required_columns=("is_pep",),
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
        raw = df["is_pep"]
        if raw.dtype == bool or raw.dtype == "boolean":
            values = raw.astype(float)
        else:
            values = raw.astype(float).clip(0.0, 1.0)

        return FeatureResult(
            values=values.rename(self.metadata.name),
            data_quality_score=quality,
            metadata=self.metadata,
        )


# Convenience: all compliance feature computers
ALL_COMPLIANCE_FEATURES: list[type[BaseFeatureComputer]] = [
    KycVerificationDays,
    AmlRiskScore,
    IdentityMatchConfidence,
    SanctionsListFlag,
    PepFlag,
]
