"""Compliance orchestration service (BRD §5.3, Phase 15.3).

Orchestrates KYC and AML checks, updates Subject entity status,
and stores compliance check history for audit trail.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.compliance_check import (
    ComplianceCheck,
    ComplianceCheckStatus,
    ComplianceCheckType,
)
from app.models.subject import AMLStatus, KYCStatus, Subject
from app.schemas.aml import AMLResult, AMLRiskRating, AMLStatusEnum
from app.schemas.kyc import (
    BiometricData,
    IDType,
    KYCResult,
    KYCStatusEnum,
)
from app.services.aml_service import ComplyAdvantageClient
from app.services.id_hasher import hash_national_id
from app.services.kyc_service import SmileIDClient

logger = structlog.get_logger(__name__)
settings = get_settings()


class ComplianceService:
    """Orchestrates KYC + AML compliance checks.

    Coordinates between the Smile ID and ComplyAdvantage clients,
    updates Subject entity compliance fields, and persists check
    history to the compliance_checks table.
    """

    def __init__(
        self,
        kyc_client: SmileIDClient | None = None,
        aml_client: ComplyAdvantageClient | None = None,
    ) -> None:
        self._kyc_client = kyc_client or SmileIDClient()
        self._aml_client = aml_client or ComplyAdvantageClient()

    async def run_kyc_check(
        self,
        db: AsyncSession,
        subject: Subject,
        national_id: str,
        id_type: IDType = IDType.NATIONAL_ID,
        biometric_data: BiometricData | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        country: str = "KE",
    ) -> KYCResult:
        """Run KYC verification and update subject status.

        Args:
            db: Async database session.
            subject: Subject entity to update.
            national_id: National ID (hashed before logging).
            id_type: Identity document type.
            biometric_data: Optional biometric data.
            first_name: First name on document.
            last_name: Last name on document.
            country: Country code.

        Returns:
            KYCResult from the verification.
        """
        id_hash = hash_national_id(national_id)
        await logger.ainfo(
            "compliance_kyc_check_started",
            subject_id=str(subject.subject_id),
            subject_id_hash=id_hash,
        )

        try:
            result = await self._kyc_client.verify_identity(
                national_id=national_id,
                id_type=id_type,
                biometric_data=biometric_data,
                first_name=first_name,
                last_name=last_name,
                country=country,
            )

            # Map KYC result status to subject status
            kyc_status_map: dict[KYCStatusEnum, KYCStatus] = {
                KYCStatusEnum.VERIFIED: KYCStatus.VERIFIED,
                KYCStatusEnum.PENDING: KYCStatus.PENDING,
                KYCStatusEnum.FAILED: KYCStatus.FAILED,
            }
            subject.kyc_status = kyc_status_map[result.status]

            # Map to compliance check status
            check_status_map: dict[KYCStatusEnum, ComplianceCheckStatus] = {
                KYCStatusEnum.VERIFIED: ComplianceCheckStatus.PASSED,
                KYCStatusEnum.PENDING: ComplianceCheckStatus.PENDING,
                KYCStatusEnum.FAILED: ComplianceCheckStatus.FAILED,
            }

            # Store compliance check record
            check = ComplianceCheck(
                check_id=uuid.uuid4(),
                subject_id=subject.subject_id,
                check_type=ComplianceCheckType.KYC,
                status=check_status_map[result.status],
                provider="smile_id",
                provider_reference=result.provider_reference,
                confidence_score=result.confidence_score,
                checked_at=result.verified_at or datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc) + timedelta(
                    days=settings.kyc_refresh_interval_days,
                ),
            )
            db.add(check)

            await logger.ainfo(
                "compliance_kyc_check_completed",
                subject_id=str(subject.subject_id),
                status=result.status.value,
            )

            return result

        except Exception as exc:
            await logger.aerror(
                "compliance_kyc_check_failed",
                subject_id=str(subject.subject_id),
                error=str(exc),
            )
            # Store failed check for audit trail
            check = ComplianceCheck(
                check_id=uuid.uuid4(),
                subject_id=subject.subject_id,
                check_type=ComplianceCheckType.KYC,
                status=ComplianceCheckStatus.FAILED,
                provider="smile_id",
                checked_at=datetime.now(timezone.utc),
            )
            db.add(check)
            raise

    async def run_aml_check(
        self,
        db: AsyncSession,
        subject: Subject,
        name: str,
        national_id: str,
        date_of_birth: str | None = None,
        nationality: str = "KE",
    ) -> AMLResult:
        """Run AML screening and update subject status.

        Args:
            db: Async database session.
            subject: Subject entity to update.
            name: Full name for screening.
            national_id: National ID (hashed before logging).
            date_of_birth: Date of birth in YYYY-MM-DD format.
            nationality: Country code.

        Returns:
            AMLResult from the screening.
        """
        id_hash = hash_national_id(national_id)
        await logger.ainfo(
            "compliance_aml_check_started",
            subject_id=str(subject.subject_id),
            subject_id_hash=id_hash,
        )

        try:
            result = await self._aml_client.screen_individual(
                name=name,
                national_id=national_id,
                date_of_birth=date_of_birth,
                nationality=nationality,
            )

            # Map AML result status to subject status
            aml_status_map: dict[AMLStatusEnum, AMLStatus] = {
                AMLStatusEnum.CLEAR: AMLStatus.CLEAR,
                AMLStatusEnum.REVIEW: AMLStatus.REVIEW,
                AMLStatusEnum.FLAGGED: AMLStatus.FLAGGED,
            }
            subject.aml_status = aml_status_map[result.status]

            # Map to compliance check status
            check_status_map: dict[AMLStatusEnum, ComplianceCheckStatus] = {
                AMLStatusEnum.CLEAR: ComplianceCheckStatus.PASSED,
                AMLStatusEnum.REVIEW: ComplianceCheckStatus.REVIEW,
                AMLStatusEnum.FLAGGED: ComplianceCheckStatus.FAILED,
            }

            # Store compliance check record
            check = ComplianceCheck(
                check_id=uuid.uuid4(),
                subject_id=subject.subject_id,
                check_type=ComplianceCheckType.AML,
                status=check_status_map[result.status],
                provider="comply_advantage",
                provider_reference=result.provider_reference,
                risk_score=result.risk_score,
                checked_at=result.screened_at or datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc) + timedelta(
                    days=settings.kyc_refresh_interval_days,
                ),
            )
            db.add(check)

            await logger.ainfo(
                "compliance_aml_check_completed",
                subject_id=str(subject.subject_id),
                status=result.status.value,
                risk_rating=result.risk_rating.value,
            )

            return result

        except Exception as exc:
            await logger.aerror(
                "compliance_aml_check_failed",
                subject_id=str(subject.subject_id),
                error=str(exc),
            )
            # Store failed check for audit trail
            check = ComplianceCheck(
                check_id=uuid.uuid4(),
                subject_id=subject.subject_id,
                check_type=ComplianceCheckType.AML,
                status=ComplianceCheckStatus.FAILED,
                provider="comply_advantage",
                checked_at=datetime.now(timezone.utc),
            )
            db.add(check)
            raise

    async def run_full_compliance_check(
        self,
        db: AsyncSession,
        subject: Subject,
        national_id: str,
        name: str,
        id_type: IDType = IDType.NATIONAL_ID,
        biometric_data: BiometricData | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        date_of_birth: str | None = None,
        nationality: str = "KE",
    ) -> dict[str, Any]:
        """Run both KYC and AML checks.

        Runs KYC first, then AML. If KYC fails, AML still runs.
        Returns results from both checks.
        """
        await logger.ainfo(
            "compliance_full_check_started",
            subject_id=str(subject.subject_id),
        )

        results: dict[str, Any] = {
            "kyc": None,
            "aml": None,
            "kyc_error": None,
            "aml_error": None,
        }

        # Run KYC
        try:
            kyc_result = await self.run_kyc_check(
                db=db,
                subject=subject,
                national_id=national_id,
                id_type=id_type,
                biometric_data=biometric_data,
                first_name=first_name,
                last_name=last_name,
                country=nationality,
            )
            results["kyc"] = kyc_result
        except Exception as exc:
            results["kyc_error"] = str(exc)

        # Run AML (even if KYC failed)
        try:
            aml_result = await self.run_aml_check(
                db=db,
                subject=subject,
                name=name,
                national_id=national_id,
                date_of_birth=date_of_birth,
                nationality=nationality,
            )
            results["aml"] = aml_result
        except Exception as exc:
            results["aml_error"] = str(exc)

        await logger.ainfo(
            "compliance_full_check_completed",
            subject_id=str(subject.subject_id),
            kyc_ok=results["kyc_error"] is None,
            aml_ok=results["aml_error"] is None,
        )

        return results

    @staticmethod
    async def get_latest_kyc_check(
        db: AsyncSession,
        subject_id: uuid.UUID,
    ) -> ComplianceCheck | None:
        """Retrieve the most recent KYC check for a subject."""
        result = await db.execute(
            select(ComplianceCheck)
            .where(
                ComplianceCheck.subject_id == subject_id,
                ComplianceCheck.check_type == ComplianceCheckType.KYC,
            )
            .order_by(ComplianceCheck.checked_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_latest_aml_check(
        db: AsyncSession,
        subject_id: uuid.UUID,
    ) -> ComplianceCheck | None:
        """Retrieve the most recent AML check for a subject."""
        result = await db.execute(
            select(ComplianceCheck)
            .where(
                ComplianceCheck.subject_id == subject_id,
                ComplianceCheck.check_type == ComplianceCheckType.AML,
            )
            .order_by(ComplianceCheck.checked_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_compliance_history(
        db: AsyncSession,
        subject_id: uuid.UUID,
        limit: int = 20,
    ) -> list[ComplianceCheck]:
        """Retrieve compliance check history for a subject."""
        result = await db.execute(
            select(ComplianceCheck)
            .where(ComplianceCheck.subject_id == subject_id)
            .order_by(ComplianceCheck.checked_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
