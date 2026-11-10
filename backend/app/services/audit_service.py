"""Audit logging service — immutable audit trail (BRD §13.3.1).

All API and authentication events are persisted to the ``api_request_logs``
table (and, for auth events, to a dedicated ``auth_events`` log).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_request_log import ApiRequestLog

logger = structlog.get_logger(__name__)


class AuditService:
    """Provides class-level helper methods for writing audit records."""

    @staticmethod
    async def log_api_request(
        db: AsyncSession,
        customer_id: str,
        endpoint: str,
        subject_id: str | None,
        response_status: int,
        response_time_ms: int,
        query_cost: int = 1,
        ip_address: str | None = None,
    ) -> ApiRequestLog:
        """Create an immutable API request log entry.

        Parameters
        ----------
        db:
            Async database session (caller is responsible for committing).
        customer_id:
            UUID of the authenticated customer.
        endpoint:
            HTTP method + path, e.g. ``"GET /v1/scores/lite/12345"``.
        subject_id:
            Optional UUID of the subject (individual/business) being queried.
        response_status:
            HTTP status code returned to the client.
        response_time_ms:
            Total response time in milliseconds.
        query_cost:
            Number of quota credits consumed (default 1).
        ip_address:
            SHA-256 hashed client IP — raw IPs must never be stored.
        """
        log_entry = ApiRequestLog(
            log_id=uuid.uuid4(),
            customer_id=uuid.UUID(customer_id) if isinstance(customer_id, str) else customer_id,
            request_time=datetime.now(timezone.utc),
            endpoint=endpoint,
            subject_id=uuid.UUID(subject_id) if isinstance(subject_id, str) else subject_id,
            response_status=response_status,
            response_time_ms=response_time_ms,
            query_cost=query_cost,
            ip_address=ip_address,
        )
        db.add(log_entry)
        return log_entry

    @staticmethod
    async def log_auth_event(
        db: AsyncSession,
        event_type: str,
        user_id: str | None,
        customer_id: str | None,
        ip_address: str,
        success: bool,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Log an authentication event.

        Supported ``event_type`` values:
        - ``login`` / ``logout``
        - ``login_failed``
        - ``password_change``
        - ``api_key_created`` / ``api_key_revoked``
        - ``account_locked`` / ``account_unlocked``

        Until a dedicated ``auth_events`` table exists, events are recorded
        as structured log lines that flow to the ELK stack.
        """
        await logger.ainfo(
            "auth_event",
            event_type=event_type,
            user_id=user_id,
            customer_id=customer_id,
            ip_address=ip_address,
            success=success,
            details=details or {},
        )
