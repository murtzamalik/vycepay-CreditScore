"""FastAPI middleware: correlation IDs, request logging, rate limiting."""

from __future__ import annotations

import time

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import generate_correlation_id

logger = structlog.get_logger(__name__)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Attach a correlation ID to every request/response for distributed tracing."""

    HEADER = "X-Correlation-ID"

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        correlation_id = request.headers.get(self.HEADER) or generate_correlation_id()
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

        response = await call_next(request)
        response.headers[self.HEADER] = correlation_id
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request with method, path, status, and duration."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        await logger.ainfo(
            "request_completed",
            method=request.method,
            path=str(request.url.path),
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory per-IP rate limiter (placeholder for Redis-backed version).

    This is intentionally naive for local development. In production, replace
    with a Redis sliding-window counter keyed by API key + tier.
    """

    def __init__(self, app, requests_per_minute: int = 120) -> None:  # noqa: ANN001
        super().__init__(app)
        self.rpm = requests_per_minute
        self._counters: dict[str, list[float]] = {}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window = self._counters.setdefault(client_ip, [])

        # Prune entries older than 60 s
        window[:] = [t for t in window if now - t < 60]

        remaining = max(0, self.rpm - len(window))
        if remaining == 0:
            return Response(
                content='{"error":{"code":"RATE_LIMITED","message":"Too many requests","details":{}}}',
                status_code=429,
                media_type="application/json",
                headers={
                    "X-RateLimit-Limit": str(self.rpm),
                    "X-RateLimit-Remaining": "0",
                },
            )

        window.append(now)
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.rpm)
        response.headers["X-RateLimit-Remaining"] = str(remaining - 1)
        return response
