"""Monthly quota enforcement per customer (BRD §7.2.7, §9.8)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import status as http_status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import VyceScoreError
from app.models.customer import Customer


@dataclass(frozen=True, slots=True)
class QuotaResult:
    """Result of a monthly quota check."""

    allowed: bool
    limit: int
    used: int
    remaining: int
    period: str  # YYYY-MM


def _quota_key(customer_id: str, period: str) -> str:
    return f"quota:{customer_id}:{period}"


def _current_period() -> str:
    """Return the current month as ``YYYY-MM``."""
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _next_period_reset(period: str) -> str:
    """Return the ISO-8601 timestamp for the start of the next period."""
    year, month = int(period.split("-")[0]), int(period.split("-")[1])
    if month == 12:
        return f"{year + 1}-01-01T00:00:00Z"
    return f"{year}-{month + 1:02d}-01T00:00:00Z"


class QuotaExceededError(VyceScoreError):
    """Monthly query quota exceeded (BRD §9.8)."""

    def __init__(self, quota: int, used: int, resets_at: str) -> None:
        super().__init__(
            code="RATE_LIMIT_EXCEEDED",
            message="Monthly query quota exceeded. Contact support to upgrade your plan.",
            status_code=http_status.HTTP_429_TOO_MANY_REQUESTS,
            details={"quota": quota, "used": used, "resetsAt": resets_at},
        )


async def check_monthly_quota(
    redis: Redis,
    db: AsyncSession,
    customer_id: str,
) -> QuotaResult:
    """Check whether *customer_id* has remaining monthly query quota.

    Usage is tracked in Redis with key ``quota:{customer_id}:{YYYY-MM}``.
    The monthly limit is read from the ``customers`` table.
    """
    period = _current_period()
    key = _quota_key(customer_id, period)

    # Fetch limit from DB
    result = await db.execute(
        select(Customer.monthly_query_limit).where(
            Customer.customer_id == customer_id
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        return QuotaResult(allowed=False, limit=0, used=0, remaining=0, period=period)
    monthly_limit: int = row

    # Current usage from Redis
    raw = await redis.get(key)
    used = int(raw) if raw else 0

    if used >= monthly_limit:
        return QuotaResult(
            allowed=False,
            limit=monthly_limit,
            used=used,
            remaining=0,
            period=period,
        )

    return QuotaResult(
        allowed=True,
        limit=monthly_limit,
        used=used,
        remaining=monthly_limit - used,
        period=period,
    )


async def enforce_monthly_quota(
    redis: Redis,
    db: AsyncSession,
    customer_id: str,
) -> QuotaResult:
    """Check quota and raise ``QuotaExceededError`` if exhausted.

    This is a convenience wrapper around :func:`check_monthly_quota` that
    raises the standard §9.8 error format when the quota is exceeded.
    """
    result = await check_monthly_quota(redis, db, customer_id)
    if not result.allowed:
        resets_at = _next_period_reset(result.period)
        raise QuotaExceededError(
            quota=result.limit,
            used=result.used,
            resets_at=resets_at,
        )
    return result


async def increment_quota(redis: Redis, customer_id: str, amount: int = 1) -> int:
    """Increment monthly usage counter and return the new total.

    The key expires at the start of the next calendar month (approximated by
    setting a 32-day TTL, which is safe because the key is period-scoped).
    """
    period = _current_period()
    key = _quota_key(customer_id, period)

    pipe = redis.pipeline()
    pipe.incrby(key, amount)
    pipe.expire(key, 32 * 86400)  # auto-expire after ~1 month
    results = await pipe.execute()
    return int(results[0])
