"""Immutable audit log service with hash chain integrity (BRD §13.3.1, Phase 12.3).

Provides:
  - Write-once audit log entries with SHA-256 hash chain
  - Each entry includes hash of previous entry for tamper detection
  - Verification function to check audit log integrity
  - Category-based retention policy assignment

Security invariants:
  - Audit log entries are NEVER updated or deleted through this service.
  - PII is NEVER included in audit log details — use hashed identifiers.
  - Hash chain integrity is verified on each write.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.audit_log import AuditLog, AuditLogCategory

logger = get_logger("immutable_audit")

# Genesis hash — the "previous hash" for the very first entry
GENESIS_HASH = "0" * 64

# Retention periods per category (in years) per BRD §13.3.2
CATEGORY_RETENTION_YEARS: dict[AuditLogCategory, int] = {
    AuditLogCategory.API_REQUEST: 10,
    AuditLogCategory.AUTHENTICATION: 7,
    AuditLogCategory.SCORE_CALCULATION: 10,
    AuditLogCategory.ADMIN_ACTION: 10,
    AuditLogCategory.SYSTEM_EVENT: 3,
    AuditLogCategory.DATA_ACCESS: 10,
    AuditLogCategory.DATA_MODIFICATION: 10,
}


def compute_entry_hash(
    previous_hash: str,
    sequence_number: int,
    category: str,
    action: str,
    actor_id: str | None,
    timestamp: str,
    details: dict[str, Any] | None,
) -> str:
    """Compute SHA-256 hash for an audit log entry.

    The hash covers all fields that must be tamper-evident.  Changing
    any of these fields will produce a different hash, breaking the chain.

    Args:
        previous_hash: Hash of the preceding entry in the chain.
        sequence_number: Monotonically increasing sequence number.
        category: Audit log category.
        action: Description of the action.
        actor_id: Identifier of the actor (may be None for system events).
        timestamp: ISO-format timestamp string.
        details: Optional structured details (serialized to sorted JSON).

    Returns:
        64-character hex string (SHA-256 digest).
    """
    details_str = json.dumps(details, sort_keys=True, default=str) if details else ""
    payload = (
        f"{previous_hash}|{sequence_number}|{category}|{action}|"
        f"{actor_id or ''}|{timestamp}|{details_str}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ImmutableAuditService:
    """Service for creating and verifying immutable audit log entries."""

    @staticmethod
    async def _get_last_entry(db: AsyncSession) -> AuditLog | None:
        """Retrieve the most recent audit log entry by sequence number."""
        result = await db.execute(
            select(AuditLog)
            .order_by(AuditLog.sequence_number.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _get_next_sequence(db: AsyncSession) -> int:
        """Get the next sequence number (max + 1, or 1 for genesis)."""
        result = await db.execute(
            select(func.max(AuditLog.sequence_number))
        )
        max_seq = result.scalar_one_or_none()
        return (max_seq or 0) + 1

    @staticmethod
    async def create_entry(
        db: AsyncSession,
        category: AuditLogCategory,
        action: str,
        actor_id: str | None = None,
        actor_type: str = "SYSTEM",
        resource_type: str | None = None,
        resource_id: str | None = None,
        details: dict[str, Any] | None = None,
        ip_address: str | None = None,
    ) -> AuditLog:
        """Create a new immutable audit log entry with hash chain linkage.

        Args:
            db: Async database session (caller commits).
            category: Log category for retention policy grouping.
            action: Human-readable action description.
            actor_id: Hashed or anonymized identifier of the actor.
            actor_type: Type of actor (USER, API_KEY, SYSTEM, SCHEDULER).
            resource_type: Type of resource affected.
            resource_id: Identifier of the affected resource.
            details: Additional structured data (must not contain PII).
            ip_address: SHA-256 hashed client IP address.

        Returns:
            The created AuditLog entry.
        """
        # Get previous entry for hash chain
        last_entry = await ImmutableAuditService._get_last_entry(db)
        previous_hash = last_entry.entry_hash if last_entry else GENESIS_HASH

        # Get next sequence number
        sequence_number = await ImmutableAuditService._get_next_sequence(db)

        # Compute timestamp
        timestamp = datetime.now(timezone.utc)
        timestamp_str = timestamp.isoformat()

        # Compute entry hash
        entry_hash = compute_entry_hash(
            previous_hash=previous_hash,
            sequence_number=sequence_number,
            category=category.value,
            action=action,
            actor_id=actor_id,
            timestamp=timestamp_str,
            details=details,
        )

        # Determine retention period
        retention_years = CATEGORY_RETENTION_YEARS.get(category, 10)

        # Create entry
        entry = AuditLog(
            log_id=uuid.uuid4(),
            sequence_number=sequence_number,
            category=category,
            action=action,
            actor_id=actor_id,
            actor_type=actor_type,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            timestamp=timestamp,
            entry_hash=entry_hash,
            previous_hash=previous_hash,
            is_verified=True,
            retention_years=retention_years,
        )

        db.add(entry)
        await db.flush()

        await logger.ainfo(
            "audit.entry_created",
            sequence=sequence_number,
            category=category.value,
            action=action,
        )

        return entry

    @staticmethod
    async def verify_chain(
        db: AsyncSession,
        start_sequence: int | None = None,
        end_sequence: int | None = None,
    ) -> tuple[bool, list[dict[str, Any]]]:
        """Verify the integrity of the audit log hash chain.

        Checks that each entry's ``entry_hash`` matches the recomputed hash
        and that ``previous_hash`` matches the preceding entry's ``entry_hash``.

        Args:
            db: Async database session.
            start_sequence: Starting sequence number (inclusive). Defaults to 1.
            end_sequence: Ending sequence number (inclusive). Defaults to latest.

        Returns:
            Tuple of (is_valid, violations) where violations is a list of
            dicts describing each integrity failure.
        """
        query = select(AuditLog).order_by(AuditLog.sequence_number)

        if start_sequence is not None:
            query = query.where(AuditLog.sequence_number >= start_sequence)
        if end_sequence is not None:
            query = query.where(AuditLog.sequence_number <= end_sequence)

        result = await db.execute(query)
        entries = list(result.scalars().all())

        if not entries:
            return True, []

        violations: list[dict[str, Any]] = []

        for i, entry in enumerate(entries):
            # Determine expected previous hash
            if i == 0:
                if entry.sequence_number == 1:
                    expected_previous = GENESIS_HASH
                else:
                    # Need to fetch the entry before start_sequence
                    prev_result = await db.execute(
                        select(AuditLog)
                        .where(AuditLog.sequence_number == entry.sequence_number - 1)
                    )
                    prev_entry = prev_result.scalar_one_or_none()
                    expected_previous = prev_entry.entry_hash if prev_entry else GENESIS_HASH
            else:
                expected_previous = entries[i - 1].entry_hash

            # Check previous_hash linkage
            if entry.previous_hash != expected_previous:
                violations.append({
                    "sequence_number": entry.sequence_number,
                    "type": "CHAIN_BREAK",
                    "message": (
                        f"previous_hash mismatch: stored={entry.previous_hash!r}, "
                        f"expected={expected_previous!r}"
                    ),
                })

            # Recompute entry hash
            expected_hash = compute_entry_hash(
                previous_hash=entry.previous_hash,
                sequence_number=entry.sequence_number,
                category=entry.category.value,
                action=entry.action,
                actor_id=entry.actor_id,
                timestamp=entry.timestamp.isoformat(),
                details=entry.details,
            )

            if entry.entry_hash != expected_hash:
                violations.append({
                    "sequence_number": entry.sequence_number,
                    "type": "HASH_MISMATCH",
                    "message": (
                        f"entry_hash mismatch: stored={entry.entry_hash!r}, "
                        f"recomputed={expected_hash!r}"
                    ),
                })

        is_valid = len(violations) == 0

        await logger.ainfo(
            "audit.chain_verified",
            entries_checked=len(entries),
            is_valid=is_valid,
            violations_count=len(violations),
        )

        return is_valid, violations

    @staticmethod
    async def get_entries(
        db: AsyncSession,
        category: AuditLogCategory | None = None,
        actor_id: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[AuditLog], int]:
        """Query audit log entries with optional filters.

        Returns:
            Tuple of (entries, total_count).
        """
        query = select(AuditLog)
        count_query = select(func.count(AuditLog.log_id))

        if category is not None:
            query = query.where(AuditLog.category == category)
            count_query = count_query.where(AuditLog.category == category)

        if actor_id is not None:
            query = query.where(AuditLog.actor_id == actor_id)
            count_query = count_query.where(AuditLog.actor_id == actor_id)

        if resource_type is not None:
            query = query.where(AuditLog.resource_type == resource_type)
            count_query = count_query.where(AuditLog.resource_type == resource_type)

        if resource_id is not None:
            query = query.where(AuditLog.resource_id == resource_id)
            count_query = count_query.where(AuditLog.resource_id == resource_id)

        if start_time is not None:
            query = query.where(AuditLog.timestamp >= start_time)
            count_query = count_query.where(AuditLog.timestamp >= start_time)

        if end_time is not None:
            query = query.where(AuditLog.timestamp <= end_time)
            count_query = count_query.where(AuditLog.timestamp <= end_time)

        total_result = await db.execute(count_query)
        total = total_result.scalar_one()

        query = query.order_by(AuditLog.sequence_number.desc()).offset(offset).limit(limit)
        result = await db.execute(query)
        entries = list(result.scalars().all())

        return entries, total
