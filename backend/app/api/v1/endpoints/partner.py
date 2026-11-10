"""Partner-facing endpoints (BRD §7.3.2, §7.2.7).

Routes:
  GET  /v1/partner/usage             — Monthly usage for authenticated partner
  GET  /v1/partner/usage/report/{month} — Detailed monthly statement
  GET  /v1/partner/usage/trend       — Usage trend over recent months
  POST /v1/partner/api-keys/rotate   — Rotate API key
  POST /v1/partner/api-keys/revoke   — Revoke current API key
  GET  /v1/partner/api-keys/info     — Get masked API key info
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status
from sqlalchemy import and_, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.core.rbac import require_permissions
from app.database import get_db
from app.models.api_request_log import ApiRequestLog
from app.models.customer import Customer
from app.schemas.billing import (
    ApiKeyInfoResponse,
    ApiKeyRevokeResponse,
    ApiKeyRotateResponse,
    DailyUsageEntry,
    MonthlyStatementResponse,
    PartnerUsageResponse,
    PartnerUsageTrendResponse,
    UsageTrendEntry,
)
from app.services.auth_service import AuthService
from app.services.billing_service import BillingService

logger = get_logger("partner_endpoints")
router = APIRouter(prefix="/partner", tags=["Partner"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_partner_customer(
    db: AsyncSession,
    current_user: dict,
) -> Customer:
    """Resolve the Customer record associated with the current partner user.

    Partners are linked to a customer via their organization/customer_id claim
    in the JWT token.
    """
    customer_id = current_user.get("customer_id")
    if customer_id is None:
        raise ForbiddenError("No customer association found for this user")

    result = await db.execute(
        select(Customer).where(Customer.customer_id == customer_id)
    )
    customer = result.scalar_one_or_none()
    if customer is None:
        raise NotFoundError("Customer", str(customer_id))
    return customer


# ---------------------------------------------------------------------------
# Usage endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/usage",
    response_model=PartnerUsageResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current month usage for authenticated partner",
)
async def get_partner_usage(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("scores:read")),
) -> PartnerUsageResponse:
    """Return monthly usage statistics for the current billing period."""
    customer = await _get_partner_customer(db, current_user)
    now = datetime.now(timezone.utc)
    year, month = now.year, now.month
    billing_period = f"{year:04d}-{month:02d}"

    counts = await BillingService.get_monthly_query_counts(
        db, str(customer.customer_id), year, month,
    )
    daily = await BillingService.get_daily_breakdown(
        db, str(customer.customer_id), year, month,
    )

    total = counts["total_queries"]
    limit = customer.monthly_query_limit
    remaining = max(0, limit - total)
    pct = (total / limit * 100.0) if limit > 0 else 0.0

    return PartnerUsageResponse(
        customer_id=str(customer.customer_id),
        customer_name=customer.name,
        tier=customer.license_tier.value,
        billing_period=billing_period,
        total_queries=total,
        lite_queries=counts["lite_queries"],
        pro_queries=counts["pro_queries"],
        batch_queries=counts["batch_queries"],
        query_limit=limit,
        queries_remaining=remaining,
        usage_percentage=round(pct, 1),
        daily_usage=[DailyUsageEntry(**d) for d in daily],
    )


@router.get(
    "/usage/report/{month}",
    response_model=MonthlyStatementResponse,
    status_code=status.HTTP_200_OK,
    summary="Get detailed monthly statement",
)
async def get_partner_usage_report(
    month: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("scores:read")),
) -> MonthlyStatementResponse:
    """Return a detailed monthly billing statement.

    ``month`` must be in ``YYYY-MM`` format.
    """
    customer = await _get_partner_customer(db, current_user)
    year_int, month_int = int(month[:4]), int(month[5:7])

    # Generate/update billing record
    record = await BillingService.generate_billing_record(
        db, str(customer.customer_id), month,
    )
    daily = await BillingService.get_daily_breakdown(
        db, str(customer.customer_id), year_int, month_int,
    )

    return MonthlyStatementResponse(
        billing_period=month,
        customer_name=customer.name,
        customer_id=str(customer.customer_id),
        tier=customer.license_tier.value,
        status=record.status.value,
        base_fee=record.base_fee,
        lite_queries=record.lite_queries,
        lite_cost=record.lite_cost,
        pro_queries=record.pro_queries,
        pro_cost=record.pro_cost,
        batch_queries=record.batch_queries,
        overage_queries=record.overage_queries,
        overage_cost=record.overage_cost,
        total_queries=record.total_queries,
        included_queries=record.included_queries,
        total_amount=record.total_amount,
        currency=record.currency,
        daily_breakdown=[DailyUsageEntry(**d) for d in daily],
        generated_at=datetime.now(timezone.utc),
    )


@router.get(
    "/usage/trend",
    response_model=PartnerUsageTrendResponse,
    status_code=status.HTTP_200_OK,
    summary="Get usage trend over recent months",
)
async def get_partner_usage_trend(
    months: int = 6,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("scores:read")),
) -> PartnerUsageTrendResponse:
    """Return usage trend over the specified number of recent months."""
    customer = await _get_partner_customer(db, current_user)
    records = await BillingService.get_customer_billing_history(
        db, str(customer.customer_id), limit=months,
    )

    trend_entries = [
        UsageTrendEntry(
            period=r.billing_period,
            total_queries=r.total_queries,
            lite_queries=r.lite_queries,
            pro_queries=r.pro_queries,
        )
        for r in records
    ]

    return PartnerUsageTrendResponse(
        customer_id=str(customer.customer_id),
        months=trend_entries,
    )


# ---------------------------------------------------------------------------
# API Key management
# ---------------------------------------------------------------------------


@router.get(
    "/api-keys/info",
    response_model=ApiKeyInfoResponse,
    status_code=status.HTTP_200_OK,
    summary="Get masked API key info",
)
async def get_api_key_info(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("scores:read")),
) -> ApiKeyInfoResponse:
    """Return masked API key information for the partner's customer."""
    customer = await _get_partner_customer(db, current_user)

    # We store the hash, not the key. Show first 8 chars of the hash as prefix.
    key_prefix = customer.api_key_hash[:8] if customer.api_key_hash else "none"

    # Get last usage time
    last_used = await db.scalar(
        select(func.max(ApiRequestLog.request_time)).where(
            ApiRequestLog.customer_id == customer.customer_id
        )
    )

    return ApiKeyInfoResponse(
        key_prefix=f"vyc_{key_prefix}...",
        created_at=customer.created_at,
        last_used_at=last_used,
    )


@router.post(
    "/api-keys/rotate",
    response_model=ApiKeyRotateResponse,
    status_code=status.HTTP_200_OK,
    summary="Rotate API key",
)
async def rotate_api_key(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("scores:read")),
) -> ApiKeyRotateResponse:
    """Rotate the partner's API key.

    The new key is returned **once**. The old key is immediately invalidated.
    """
    customer = await _get_partner_customer(db, current_user)

    # Generate new key
    raw_key, key_hash = AuthService.generate_api_key()

    # Immediately update — old key is now invalid
    customer.api_key_hash = key_hash
    await db.flush()

    await logger.ainfo(
        "partner.api_key_rotated",
        customer_id=str(customer.customer_id),
    )

    return ApiKeyRotateResponse(api_key=raw_key)


@router.post(
    "/api-keys/revoke",
    response_model=ApiKeyRevokeResponse,
    status_code=status.HTTP_200_OK,
    summary="Revoke current API key",
)
async def revoke_api_key(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("scores:read")),
) -> ApiKeyRevokeResponse:
    """Revoke the partner's API key. They will need to request a new one from admin."""
    customer = await _get_partner_customer(db, current_user)

    customer.api_key_hash = None
    await db.flush()

    await logger.ainfo(
        "partner.api_key_revoked",
        customer_id=str(customer.customer_id),
    )

    return ApiKeyRevokeResponse()
