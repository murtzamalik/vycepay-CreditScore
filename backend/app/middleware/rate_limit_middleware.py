"""Rate-limit middleware that adds standard headers to all responses (BRD §9.9).

For authenticated requests (those with a resolved customer), the middleware
checks the sliding-window rate limiter and returns 429 when the limit is
exceeded.  Rate-limit headers are always attached to the response.
"""

from __future__ import annotations

import hashlib
import time

import structlog
from redis.asyncio import Redis
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import get_settings
from app.core.rate_limiter import RateLimiter, TIER_RATE_LIMITS
from app.models.customer import LicenseTier

logger = structlog.get_logger(__name__)
settings = get_settings()


class RateLimitHeaderMiddleware(BaseHTTPMiddleware):
    """Attach ``X-RateLimit-*`` headers and enforce per-customer rate limits.

    The middleware relies on upstream authentication middleware/dependency
    to set ``request.state.customer_id`` and ``request.state.license_tier``
    on the request.  If those attributes are absent the request is passed
    through without rate-limit enforcement (e.g. health-check, docs).
    """

    def __init__(self, app, redis: Redis) -> None:  # noqa: ANN001
        super().__init__(app)
        self.limiter = RateLimiter(redis)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint,
    ) -> Response:
        customer_id: str | None = getattr(request.state, "customer_id", None)
        tier_raw: str | None = getattr(request.state, "license_tier", None)

        # No customer context → skip rate limiting
        if customer_id is None or tier_raw is None:
            return await call_next(request)

        try:
            tier = LicenseTier(tier_raw)
        except ValueError:
            tier = LicenseTier.LITE

        result = await self.limiter.check_rate_limit(customer_id, tier)

        if not result.allowed:
            await logger.awarning(
                "rate_limit_exceeded",
                customer_id=customer_id,
                tier=tier.value,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "RATE_LIMITED",
                        "message": "Too many requests. Please retry after the rate limit window resets.",
                        "details": {
                            "limit": result.limit,
                            "reset": result.reset,
                            "window_seconds": result.window,
                        },
                    }
                },
                headers={
                    "X-RateLimit-Limit": str(result.limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(result.reset),
                    "X-RateLimit-Window": str(result.window),
                    "Retry-After": str(result.reset - int(time.time())),
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(result.limit)
        response.headers["X-RateLimit-Remaining"] = str(result.remaining)
        response.headers["X-RateLimit-Reset"] = str(result.reset)
        response.headers["X-RateLimit-Window"] = str(result.window)
        return response
