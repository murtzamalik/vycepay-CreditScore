"""Compliance Feature Bridge (BRD §5.3, Phase 15.4).

Bridges compliance check results (KYC/AML) into the ML feature pipeline.
Converts KYC/AML provider results into numerical feature values that
the scoring model can consume.

Features produced:
  - kyc_verification_days: days since last KYC verification
  - aml_risk_score: numeric risk score from AML screening (0-1)
  - identity_match_confidence: biometric match confidence (0-1)
  - sanctions_list_flag: 1 if on sanctions list, 0 otherwise
  - pep_flag: 1 if PEP, 0 otherwise
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compliance_check import (
    ComplianceCheck,
    ComplianceCheckStatus,
    ComplianceCheckType,
)

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ComplianceFeatures:
    """Feature values derived from compliance check results.

    All features are numerical for direct consumption by ML models.
    """

    kyc_verification_days: float | None
    """Days since last successful KYC verification. None if never verified."""

    aml_risk_score: float | None
    """AML risk score from latest screening (0.0 = lowest, 1.0 = highest). None if never screened."""

    identity_match_confidence: float | None
    """Biometric identity match confidence (0.0 = no match, 1.0 = perfect). None if no biometric check."""

    sanctions_list_flag: float
    """1.0 if on sanctions list, 0.0 otherwise."""

    pep_flag: float
    """1.0 if Politically Exposed Person, 0.0 otherwise."""

    def to_dict(self) -> dict[str, float | None]:
        """Convert to dictionary for feature store ingestion."""
        return {
            "kyc_verification_days": self.kyc_verification_days,
            "aml_risk_score": self.aml_risk_score,
            "identity_match_confidence": self.identity_match_confidence,
            "sanctions_list_flag": self.sanctions_list_flag,
            "pep_flag": self.pep_flag,
        }


class ComplianceFeatureBridge:
    """Extracts ML features from compliance check results.

    Reads the latest KYC and AML check records for a subject and
    transforms them into numerical feature values aligned with
    the ML feature definitions in ``ml/features/compliance_features.py``.
    """

    async def extract_features(
        self,
        db: AsyncSession,
        subject_id: uuid.UUID,
        reference_date: datetime | None = None,
    ) -> ComplianceFeatures:
        """Extract compliance features for a subject.

        Args:
            db: Async database session.
            subject_id: UUID of the subject.
            reference_date: Reference date for computing time-based
                features. Defaults to current UTC time.

        Returns:
            ComplianceFeatures with all computed feature values.
        """
        ref = reference_date or datetime.now(timezone.utc)

        # Fetch latest KYC and AML checks
        latest_kyc = await self._get_latest_check(
            db, subject_id, ComplianceCheckType.KYC,
        )
        latest_aml = await self._get_latest_check(
            db, subject_id, ComplianceCheckType.AML,
        )

        # Compute features
        kyc_verification_days = self._compute_kyc_days(latest_kyc, ref)
        identity_match_confidence = self._compute_identity_confidence(latest_kyc)
        aml_risk_score = self._compute_aml_risk_score(latest_aml)
        sanctions_flag = self._compute_sanctions_flag(latest_aml)
        pep_flag_value = self._compute_pep_flag(latest_aml)

        features = ComplianceFeatures(
            kyc_verification_days=kyc_verification_days,
            aml_risk_score=aml_risk_score,
            identity_match_confidence=identity_match_confidence,
            sanctions_list_flag=sanctions_flag,
            pep_flag=pep_flag_value,
        )

        await logger.ainfo(
            "compliance_features_extracted",
            subject_id=str(subject_id),
            kyc_days=kyc_verification_days,
            aml_score=aml_risk_score,
            identity_confidence=identity_match_confidence,
            sanctioned=sanctions_flag,
            pep=pep_flag_value,
        )

        return features

    @staticmethod
    async def _get_latest_check(
        db: AsyncSession,
        subject_id: uuid.UUID,
        check_type: ComplianceCheckType,
    ) -> ComplianceCheck | None:
        """Fetch the latest compliance check of a given type."""
        result = await db.execute(
            select(ComplianceCheck)
            .where(
                ComplianceCheck.subject_id == subject_id,
                ComplianceCheck.check_type == check_type,
            )
            .order_by(ComplianceCheck.checked_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _compute_kyc_days(
        check: ComplianceCheck | None,
        reference_date: datetime,
    ) -> float | None:
        """Compute days since last successful KYC verification."""
        if check is None or check.status != ComplianceCheckStatus.PASSED:
            return None
        if check.checked_at is None:
            return None
        checked_at = check.checked_at
        if isinstance(checked_at, str):
            checked_at = datetime.fromisoformat(checked_at)
        if checked_at.tzinfo is None:
            checked_at = checked_at.replace(tzinfo=timezone.utc)
        delta = reference_date - checked_at
        days = delta.total_seconds() / 86400.0
        return max(days, 0.0)

    @staticmethod
    def _compute_identity_confidence(
        check: ComplianceCheck | None,
    ) -> float | None:
        """Extract identity match confidence from the latest KYC check."""
        if check is None:
            return None
        if check.confidence_score is not None:
            return max(0.0, min(float(check.confidence_score), 1.0))
        return None

    @staticmethod
    def _compute_aml_risk_score(
        check: ComplianceCheck | None,
    ) -> float | None:
        """Extract AML risk score from the latest AML check."""
        if check is None:
            return None
        if check.risk_score is not None:
            return max(0.0, min(float(check.risk_score), 1.0))
        return None

    @staticmethod
    def _compute_sanctions_flag(
        check: ComplianceCheck | None,
    ) -> float:
        """Determine if the subject is on a sanctions list.

        Returns 1.0 if the AML check failed (FLAGGED) with a high
        risk score, 0.0 otherwise.
        """
        if check is None:
            return 0.0
        if (
            check.status == ComplianceCheckStatus.FAILED
            and check.risk_score is not None
            and float(check.risk_score) >= 0.9
        ):
            return 1.0
        return 0.0

    @staticmethod
    def _compute_pep_flag(
        check: ComplianceCheck | None,
    ) -> float:
        """Determine if the subject is a PEP.

        Returns 1.0 if the AML check is in REVIEW status (PEP or
        medium risk), 0.0 otherwise. The REVIEW status from AML
        screening specifically indicates PEP or medium-risk hits.
        """
        if check is None:
            return 0.0
        if check.status == ComplianceCheckStatus.REVIEW:
            return 1.0
        return 0.0
