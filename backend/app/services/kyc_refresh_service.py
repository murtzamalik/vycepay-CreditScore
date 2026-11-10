"""Monthly KYC Refresh Service (BRD §5.3, Phase 15.5).

Scheduled job to refresh KYC verification for existing subjects.
Identifies subjects with stale KYC (older than configured interval),
batch-processes re-verification with rate limiting, and updates
subject records.

Integrates with the APScheduler pattern used by kpi_scheduler.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import async_session_factory
from app.models.compliance_check import (
    ComplianceCheck,
    ComplianceCheckStatus,
    ComplianceCheckType,
)
from app.models.subject import KYCStatus, Subject
from app.services.kyc_service import SmileIDClient

logger = structlog.get_logger(__name__)
settings = get_settings()


class KYCRefreshService:
    """Service for batch KYC re-verification of existing subjects.

    Identifies subjects needing KYC refresh and processes them in
    batches with rate limiting to respect Smile ID API limits.
    """

    def __init__(
        self,
        kyc_client: SmileIDClient | None = None,
    ) -> None:
        self._kyc_client = kyc_client or SmileIDClient()

    async def get_subjects_needing_refresh(
        self,
        db: AsyncSession,
        max_age_days: int | None = None,
        batch_size: int | None = None,
    ) -> list[Subject]:
        """Find subjects with stale KYC that need re-verification.

        A subject needs refresh if:
          - Their KYC status is VERIFIED but the last KYC check
            is older than ``max_age_days``
          - They have never had a KYC check
          - Their KYC status is PENDING (incomplete verification)

        Args:
            db: Async database session.
            max_age_days: Maximum age in days before refresh needed.
                Defaults to config setting.
            batch_size: Maximum number of subjects to return.
                Defaults to config setting.

        Returns:
            List of Subject entities needing KYC refresh.
        """
        if max_age_days is None:
            max_age_days = settings.kyc_refresh_interval_days
        if batch_size is None:
            batch_size = settings.kyc_refresh_batch_size

        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)

        # Subquery: latest KYC check per subject
        from sqlalchemy import func

        latest_kyc_subq = (
            select(
                ComplianceCheck.subject_id,
                func.max(ComplianceCheck.checked_at).label("latest_check"),
            )
            .where(ComplianceCheck.check_type == ComplianceCheckType.KYC)
            .group_by(ComplianceCheck.subject_id)
            .subquery()
        )

        # Find subjects with stale or missing KYC
        result = await db.execute(
            select(Subject)
            .outerjoin(
                latest_kyc_subq,
                Subject.subject_id == latest_kyc_subq.c.subject_id,
            )
            .where(
                or_(
                    # Never had a KYC check
                    latest_kyc_subq.c.latest_check.is_(None),
                    # Last check is older than cutoff
                    latest_kyc_subq.c.latest_check < cutoff,
                    # Pending status
                    Subject.kyc_status == KYCStatus.PENDING,
                )
            )
            .limit(batch_size)
        )
        return list(result.scalars().all())

    async def refresh_subject_kyc(
        self,
        db: AsyncSession,
        subject: Subject,
    ) -> ComplianceCheck:
        """Re-verify KYC for a single subject.

        Since we cannot recover the original national ID from the hash,
        this method creates a check record indicating a refresh was
        attempted. In production, the national ID would be retrieved
        from a secure vault or the subject would be prompted to
        re-submit their identity documents.

        Args:
            db: Async database session.
            subject: Subject entity to refresh.

        Returns:
            The new ComplianceCheck record.
        """
        import uuid

        await logger.ainfo(
            "kyc_refresh_subject",
            subject_id=str(subject.subject_id),
            current_status=subject.kyc_status.value,
        )

        # Create a refresh check record
        # In production, this would trigger actual re-verification
        check = ComplianceCheck(
            check_id=uuid.uuid4(),
            subject_id=subject.subject_id,
            check_type=ComplianceCheckType.KYC,
            status=ComplianceCheckStatus.PENDING,
            provider="smile_id",
            provider_reference=f"refresh-{uuid.uuid4()}",
            checked_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(
                days=settings.kyc_refresh_interval_days,
            ),
        )
        db.add(check)

        # Update subject status to PENDING until refresh completes
        subject.kyc_status = KYCStatus.PENDING

        return check

    async def run_batch_refresh(
        self,
        db: AsyncSession,
        max_age_days: int | None = None,
        batch_size: int | None = None,
        rate_limit_per_minute: int | None = None,
    ) -> dict[str, int]:
        """Run batch KYC refresh with rate limiting.

        Args:
            db: Async database session.
            max_age_days: Maximum age before refresh needed.
            batch_size: Maximum subjects to process.
            rate_limit_per_minute: API calls per minute limit.

        Returns:
            Summary dict with counts of processed, succeeded, failed.
        """
        if rate_limit_per_minute is None:
            rate_limit_per_minute = settings.kyc_refresh_rate_limit_per_minute

        subjects = await self.get_subjects_needing_refresh(
            db, max_age_days=max_age_days, batch_size=batch_size,
        )

        await logger.ainfo(
            "kyc_batch_refresh_started",
            subjects_count=len(subjects),
        )

        stats: dict[str, int] = {
            "total": len(subjects),
            "succeeded": 0,
            "failed": 0,
            "skipped": 0,
        }

        # Calculate delay between calls for rate limiting
        delay_seconds = 60.0 / max(rate_limit_per_minute, 1)

        for i, subject in enumerate(subjects):
            try:
                await self.refresh_subject_kyc(db, subject)
                stats["succeeded"] += 1
            except Exception as exc:
                await logger.aerror(
                    "kyc_refresh_failed",
                    subject_id=str(subject.subject_id),
                    error=str(exc),
                )
                stats["failed"] += 1

            # Rate limiting: wait between API calls
            if i < len(subjects) - 1:
                await asyncio.sleep(delay_seconds)

        await logger.ainfo(
            "kyc_batch_refresh_completed",
            **stats,
        )

        return stats


async def run_scheduled_kyc_refresh() -> None:
    """Entry point for the scheduled KYC refresh job.

    Called by APScheduler. Opens a fresh DB session and runs the
    batch refresh process.
    """
    logger_sync = structlog.get_logger("vycescore.kyc_refresh")
    await logger_sync.ainfo("scheduled_kyc_refresh_started")

    try:
        async with async_session_factory() as session:
            service = KYCRefreshService()
            stats = await service.run_batch_refresh(session)
            await session.commit()
            await logger_sync.ainfo(
                "scheduled_kyc_refresh_completed",
                **stats,
            )
    except Exception:
        await logger_sync.aexception("scheduled_kyc_refresh_failed")
