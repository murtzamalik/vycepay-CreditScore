"""Request audit-logging middleware (BRD §13.3.1).

Automatically logs every API request to the ``api_request_logs`` table via
:class:`~app.services.audit_service.AuditService`.  Client IP addresses are
SHA-256 hashed before storage to comply with PII requirements.
"""

from __future__ import annotations

import hashlib
import time

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.database import async_session_factory
from app.services.audit_service import AuditService

logger = structlog.get_logger(__name__)


def _hash_ip(ip: str) -> str:
    """Return a SHA-256 hex digest of an IP address."""
    return hashlib.sha256(ip.encode("utf-8")).hexdigest()


class AuditLoggingMiddleware(BaseHTTPMiddleware):
    """Log every API request with timing and customer context."""

    # Paths to skip auditing (health checks, docs, etc.)
    SKIP_PATHS: frozenset[str] = frozenset({
        "/health",
        "/healthz",
        "/readyz",
        "/docs",
        "/redoc",
        "/openapi.json",
    })

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint,
    ) -> Response:
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000)

        # Extract customer context set by auth middleware
        customer_id: str | None = getattr(request.state, "customer_id", None)
        subject_id: str | None = getattr(request.state, "subject_id", None)

        # Only log if there is a customer context (authenticated request)
        if customer_id is not None:
            client_ip = request.client.host if request.client else "unknown"
            hashed_ip = _hash_ip(client_ip)

            try:
                async with async_session_factory() as session:
                    await AuditService.log_api_request(
                        db=session,
                        customer_id=customer_id,
                        endpoint=f"{request.method} {request.url.path}",
                        subject_id=subject_id,
                        response_status=response.status_code,
                        response_time_ms=duration_ms,
                        query_cost=1,
                        ip_address=hashed_ip,
                    )
                    await session.commit()
            except Exception:
                # Audit logging must never break the request flow
                await logger.aexception(
                    "audit_log_failed",
                    customer_id=customer_id,
                    endpoint=request.url.path,
                )

        return response
