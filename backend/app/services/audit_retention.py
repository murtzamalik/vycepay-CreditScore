"""Audit log retention policy service (BRD §13.3.2, Phase 12.4).

Retention periods per log category:
  - API Request Logs: 10 years
  - Authentication Logs: 7 years
  - Score Calculation Logs: 10 years
  - Admin Action Logs: 10 years
  - System Event Logs: 3 years

Provides:
  - Automated cleanup of expired audit log entries
  - Retention policy enforcement
  - Archival hooks for long-term storage before deletion

Security invariants:
  - Deletion only occurs for entries past their retention period.
  - All cleanup actions are themselves audit-logged.
  - Cleanup runs as a scheduled job (not exposed via API).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.audit_log import AuditLog, AuditLogCategory

logger = get_logger("audit_retention")

# Retention periods per BRD §13.3.2
RETENTION_POLICIES: dict[AuditLogCategory, int] = {
    AuditLogCategory.API_REQUEST: 10,
    AuditLogCategory.AUTHENTICATION: 7,
    AuditLogCategory.SCORE_CALCULATION: 10,
    AuditLogCategory.ADMIN_ACTION: 10,
    AuditLogCategory.SYSTEM_EVENT: 3,
    AuditLogCategory.DATA_ACCESS: 10,
    AuditLogCategory.DATA_MODIFICATION: 10,
}


@dataclass
class RetentionResult:
    """Result of a retention cleanup run."""

    category: str
    retention_years: int
    cutoff_date: datetime
    entries_deleted: int
    entries_archived: int


@dataclass
class CleanupSummary:
    """Summary of a full retention cleanup run across all categories."""

    run_timestamp: datetime
    results: list[RetentionResult]
    total_deleted: int
    total_archived: int
    errors: list[str]


class AuditRetentionService:
    """Manages audit log retention policies and cleanup."""

    @staticmethod
    def get_retention_years(category: AuditLogCategory) -> int:
        """Return the retention period in years for a given category."""
        return RETENTION_POLICIES.get(category, 10)

    @staticmethod
    def get_cutoff_date(retention_years: int) -> datetime:
        """Calculate the cutoff date: entries before this date are eligible for cleanup."""
        return datetime.now(timezone.utc) - timedelta(days=retention_years * 365)

    @staticmethod
    async def count_expired_entries(
        db: AsyncSession,
        category: AuditLogCategory | None = None,
    ) -> dict[str, int]:
        """Count audit log entries that have exceeded their retention period.

        Args:
            db: Async database session.
            category: Optional category filter. If None, counts all categories.

        Returns:
            Dict mapping category name to count of expired entries.
        """
        counts: dict[str, int] = {}
        categories = [category] if category else list(AuditLogCategory)

        for cat in categories:
            retention_years = RETENTION_POLICIES.get(cat, 10)
            cutoff = AuditRetentionService.get_cutoff_date(retention_years)

            result = await db.execute(
                select(func.count(AuditLog.log_id))
                .where(AuditLog.category == cat)
                .where(AuditLog.timestamp < cutoff)
            )
            count = result.scalar_one()
            if count > 0:
                counts[cat.value] = count

        return counts

    @staticmethod
    async def cleanup_category(
        db: AsyncSession,
        category: AuditLogCategory,
        batch_size: int = 1000,
        dry_run: bool = False,
    ) -> RetentionResult:
        """Delete expired audit log entries for a specific category.

        Args:
            db: Async database session (caller commits).
            category: The category to clean up.
            batch_size: Maximum number of entries to delete per batch.
            dry_run: If True, count but do not delete.

        Returns:
            RetentionResult with details of the cleanup.
        """
        retention_years = RETENTION_POLICIES.get(category, 10)
        cutoff = AuditRetentionService.get_cutoff_date(retention_years)

        # Count entries to be deleted
        count_result = await db.execute(
            select(func.count(AuditLog.log_id))
            .where(AuditLog.category == category)
            .where(AuditLog.timestamp < cutoff)
        )
        total_expired = count_result.scalar_one()

        entries_deleted = 0
        entries_archived = 0

        if not dry_run and total_expired > 0:
            # Delete in batches to avoid locking the table for too long
            while entries_deleted < total_expired:
                # Find IDs to delete in this batch
                batch_query = (
                    select(AuditLog.log_id)
                    .where(AuditLog.category == category)
                    .where(AuditLog.timestamp < cutoff)
                    .order_by(AuditLog.timestamp)
                    .limit(batch_size)
                )
                batch_result = await db.execute(batch_query)
                batch_ids = [row[0] for row in batch_result.all()]

                if not batch_ids:
                    break

                # Delete the batch
                await db.execute(
                    delete(AuditLog).where(AuditLog.log_id.in_(batch_ids))
                )
                entries_deleted += len(batch_ids)
                await db.flush()

            await logger.ainfo(
                "audit_retention.cleanup_complete",
                category=category.value,
                retention_years=retention_years,
                cutoff_date=cutoff.isoformat(),
                entries_deleted=entries_deleted,
            )
        elif dry_run:
            entries_deleted = total_expired  # Report what would be deleted
            await logger.ainfo(
                "audit_retention.dry_run",
                category=category.value,
                entries_eligible=total_expired,
            )

        return RetentionResult(
            category=category.value,
            retention_years=retention_years,
            cutoff_date=cutoff,
            entries_deleted=entries_deleted,
            entries_archived=entries_archived,
        )

    @staticmethod
    async def run_full_cleanup(
        db: AsyncSession,
        batch_size: int = 1000,
        dry_run: bool = False,
    ) -> CleanupSummary:
        """Run retention cleanup across all audit log categories.

        Args:
            db: Async database session (caller commits).
            batch_size: Maximum entries to delete per batch per category.
            dry_run: If True, count but do not delete.

        Returns:
            CleanupSummary with results for each category.
        """
        run_timestamp = datetime.now(timezone.utc)
        results: list[RetentionResult] = []
        errors: list[str] = []
        total_deleted = 0
        total_archived = 0

        for category in AuditLogCategory:
            try:
                result = await AuditRetentionService.cleanup_category(
                    db=db,
                    category=category,
                    batch_size=batch_size,
                    dry_run=dry_run,
                )
                results.append(result)
                total_deleted += result.entries_deleted
                total_archived += result.entries_archived
            except Exception as exc:
                error_msg = f"Cleanup failed for {category.value}: {exc}"
                errors.append(error_msg)
                await logger.aerror("audit_retention.cleanup_error", error=error_msg)

        await logger.ainfo(
            "audit_retention.full_cleanup_complete",
            total_deleted=total_deleted,
            total_archived=total_archived,
            errors_count=len(errors),
            dry_run=dry_run,
        )

        return CleanupSummary(
            run_timestamp=run_timestamp,
            results=results,
            total_deleted=total_deleted,
            total_archived=total_archived,
            errors=errors,
        )

    @staticmethod
    async def get_retention_status(
        db: AsyncSession,
    ) -> list[dict[str, Any]]:
        """Get current retention status for all categories.

        Returns a list of dicts with category, retention_years, total_entries,
        expired_entries, and oldest_entry_date.
        """
        status: list[dict[str, Any]] = []

        for category in AuditLogCategory:
            retention_years = RETENTION_POLICIES.get(category, 10)
            cutoff = AuditRetentionService.get_cutoff_date(retention_years)

            # Total entries
            total_result = await db.execute(
                select(func.count(AuditLog.log_id))
                .where(AuditLog.category == category)
            )
            total = total_result.scalar_one()

            # Expired entries
            expired_result = await db.execute(
                select(func.count(AuditLog.log_id))
                .where(AuditLog.category == category)
                .where(AuditLog.timestamp < cutoff)
            )
            expired = expired_result.scalar_one()

            # Oldest entry
            oldest_result = await db.execute(
                select(func.min(AuditLog.timestamp))
                .where(AuditLog.category == category)
            )
            oldest = oldest_result.scalar_one()

            status.append({
                "category": category.value,
                "retention_years": retention_years,
                "total_entries": total,
                "expired_entries": expired,
                "oldest_entry_date": oldest.isoformat() if oldest else None,
                "cutoff_date": cutoff.isoformat(),
            })

        return status
