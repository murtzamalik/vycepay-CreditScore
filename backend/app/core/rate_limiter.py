"""Redis-backed distributed rate limiter using sliding window algorithm (BRD §9.9)."""

from __future__ import annotations

import time
from dataclasses import dataclass

from redis.asyncio import Redis

from app.config import get_settings
from app.models.customer import LicenseTier

settings = get_settings()

# Tier-based rate limits (requests per hour)
TIER_RATE_LIMITS: dict[LicenseTier, int] = {
    LicenseTier.LITE: settings.rate_limit_lite_per_hour,
    LicenseTier.PRO: settings.rate_limit_pro_per_hour,
    LicenseTier.DEEP_DIVE: settings.rate_limit_deep_dive_per_hour,
}

# Window duration in seconds (1 hour)
RATE_LIMIT_WINDOW: int = 3600


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    """Result of a rate limit check."""

    allowed: bool
    limit: int
    remaining: int
    reset: int  # Unix timestamp when the window resets
    window: int  # Window duration in seconds


class RateLimiter:
    """Sliding-window rate limiter backed by Redis sorted sets.

    Each request is recorded as a member in a sorted set keyed by customer ID.
    The score is the Unix timestamp of the request. Old entries outside the
    window are pruned on every check, giving a true sliding window.
    """

    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    def _key(self, customer_id: str) -> str:
        return f"rate_limit:{customer_id}"

    async def check_rate_limit(
        self, customer_id: str, tier: LicenseTier,
    ) -> RateLimitResult:
        """Check whether the request is within the customer's tier rate limit.

        Uses a Redis sorted set with timestamps as scores. Members older than
        the window are removed atomically with the count check via a pipeline.
        """
        limit = TIER_RATE_LIMITS.get(tier, TIER_RATE_LIMITS[LicenseTier.LITE])
        now = time.time()
        window_start = now - RATE_LIMIT_WINDOW
        key = self._key(customer_id)

        pipe = self.redis.pipeline()
        # Remove entries outside the sliding window
        pipe.zremrangebyscore(key, 0, window_start)
        # Count entries in the current window
        pipe.zcard(key)
        results = await pipe.execute()

        current_count: int = results[1]

        if current_count >= limit:
            # Find the oldest entry to compute reset time
            oldest = await self.redis.zrange(key, 0, 0, withscores=True)
            reset_at = int(oldest[0][1] + RATE_LIMIT_WINDOW) if oldest else int(now + RATE_LIMIT_WINDOW)
            return RateLimitResult(
                allowed=False,
                limit=limit,
                remaining=0,
                reset=reset_at,
                window=RATE_LIMIT_WINDOW,
            )

        # Record this request — use timestamp + counter suffix to guarantee uniqueness
        member = f"{now}:{customer_id}:{current_count}"
        pipe2 = self.redis.pipeline()
        pipe2.zadd(key, {member: now})
        pipe2.expire(key, RATE_LIMIT_WINDOW + 60)  # TTL slightly beyond the window
        await pipe2.execute()

        remaining = max(0, limit - current_count - 1)
        reset_at = int(now + RATE_LIMIT_WINDOW)

        return RateLimitResult(
            allowed=True,
            limit=limit,
            remaining=remaining,
            reset=reset_at,
            window=RATE_LIMIT_WINDOW,
        )

    async def reset(self, customer_id: str) -> None:
        """Reset rate limit counter for a customer (admin operation)."""
        await self.redis.delete(self._key(customer_id))
