"""Billing and embed configuration admin endpoints (BRD §7.3.2, §7.2.7).

Routes:
  GET  /v1/admin/billing/customers/{id}/statement/{month} — Admin: monthly statement
  POST /v1/admin/billing/customers/{id}/generate/{month}  — Admin: generate billing record
  POST /v1/admin/customers/{id}/embed-config               — Save embed config
  GET  /v1/embed/config/{customerToken}                     — Public: retrieve embed config
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.core.rbac import require_permissions
from app.database import get_db
from app.models.billing import EmbedConfig
from app.models.customer import Customer
from app.schemas.billing import (
    BillingRecordResponse,
    DailyUsageEntry,
    EmbedConfigRequest,
    EmbedConfigResponse,
    MonthlyStatementResponse,
    PublicEmbedConfigResponse,
)
from app.services.billing_service import BillingService

logger = get_logger("billing_endpoints")

# We use two routers: one for admin billing, one for public embed config
billing_router = APIRouter(prefix="/admin/billing", tags=["Billing (Admin)"])
embed_admin_router = APIRouter(prefix="/admin/customers", tags=["Embed Config (Admin)"])
embed_public_router = APIRouter(prefix="/embed", tags=["Embed Config (Public)"])


# ---------------------------------------------------------------------------
# Admin billing endpoints
# ---------------------------------------------------------------------------


@billing_router.get(
    "/customers/{customer_id}/statement/{month}",
    response_model=MonthlyStatementResponse,
    status_code=status.HTTP_200_OK,
    summary="Get monthly billing statement for a customer (Admin)",
)
async def get_customer_statement(
    customer_id: str,
    month: str,
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(require_permissions("customers:read")),
) -> MonthlyStatementResponse:
    """Admin endpoint: return detailed monthly billing statement for a customer."""
    # Verify customer exists
    result = await db.execute(
        select(Customer).where(Customer.customer_id == customer_id)
    )
    customer = result.scalar_one_or_none()
    if customer is None:
        raise NotFoundError("Customer", customer_id)

    year_int, month_int = int(month[:4]), int(month[5:7])

    record = await BillingService.generate_billing_record(db, customer_id, month)
    daily = await BillingService.get_daily_breakdown(
        db, customer_id, year_int, month_int,
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


@billing_router.post(
    "/customers/{customer_id}/generate/{month}",
    response_model=BillingRecordResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate billing record for a customer (Admin)",
)
async def generate_billing_record(
    customer_id: str,
    month: str,
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(require_permissions("customers:write")),
) -> BillingRecordResponse:
    """Admin endpoint: generate or refresh a billing record."""
    record = await BillingService.generate_billing_record(db, customer_id, month)

    return BillingRecordResponse(
        billing_id=str(record.billing_id),
        customer_id=str(record.customer_id),
        billing_period=record.billing_period,
        status=record.status.value,
        lite_queries=record.lite_queries,
        pro_queries=record.pro_queries,
        batch_queries=record.batch_queries,
        total_queries=record.total_queries,
        base_fee=record.base_fee,
        lite_cost=record.lite_cost,
        pro_cost=record.pro_cost,
        overage_cost=record.overage_cost,
        total_amount=record.total_amount,
        currency=record.currency,
        included_queries=record.included_queries,
        overage_queries=record.overage_queries,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


# ---------------------------------------------------------------------------
# Embed config admin endpoints
# ---------------------------------------------------------------------------


@embed_admin_router.post(
    "/{customer_id}/embed-config",
    response_model=EmbedConfigResponse,
    status_code=status.HTTP_200_OK,
    summary="Save embed configuration for a customer",
)
async def save_embed_config(
    customer_id: str,
    body: EmbedConfigRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(require_permissions("customers:write")),
) -> EmbedConfigResponse:
    """Create or update the white-label embed configuration for a customer."""
    # Verify customer exists
    result = await db.execute(
        select(Customer).where(Customer.customer_id == customer_id)
    )
    customer = result.scalar_one_or_none()
    if customer is None:
        raise NotFoundError("Customer", customer_id)

    # Check for existing config
    existing = await db.execute(
        select(EmbedConfig).where(EmbedConfig.customer_id == customer_id)
    )
    embed_config = existing.scalar_one_or_none()

    if embed_config is not None:
        embed_config.allowed_origins = body.allowed_origins
        embed_config.theme_config = body.theme_config
        embed_config.widget_config = body.widget_config
    else:
        customer_token = secrets.token_urlsafe(32)
        embed_config = EmbedConfig(
            customer_id=customer_id,
            customer_token=customer_token,
            allowed_origins=body.allowed_origins,
            theme_config=body.theme_config,
            widget_config=body.widget_config,
        )
        db.add(embed_config)

    await db.flush()

    await logger.ainfo(
        "embed.config_saved",
        customer_id=customer_id,
    )

    return EmbedConfigResponse(
        embed_config_id=str(embed_config.embed_config_id),
        customer_id=str(embed_config.customer_id),
        customer_token=embed_config.customer_token,
        allowed_origins=embed_config.allowed_origins or [],
        theme_config=embed_config.theme_config,
        widget_config=embed_config.widget_config,
        is_active=embed_config.is_active,
        created_at=embed_config.created_at,
        updated_at=embed_config.updated_at,
    )


# ---------------------------------------------------------------------------
# Public embed config endpoint
# ---------------------------------------------------------------------------


@embed_public_router.get(
    "/config/{customer_token}",
    response_model=PublicEmbedConfigResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve embed config (public endpoint)",
)
async def get_public_embed_config(
    customer_token: str,
    db: AsyncSession = Depends(get_db),
) -> PublicEmbedConfigResponse:
    """Public endpoint for widget initialization — no auth required."""
    result = await db.execute(
        select(EmbedConfig).where(
            EmbedConfig.customer_token == customer_token,
            EmbedConfig.is_active.is_(True),
        )
    )
    embed_config = result.scalar_one_or_none()
    if embed_config is None:
        raise NotFoundError("EmbedConfig", customer_token)

    return PublicEmbedConfigResponse(
        customer_token=embed_config.customer_token,
        allowed_origins=embed_config.allowed_origins or [],
        theme_config=embed_config.theme_config,
        widget_config=embed_config.widget_config,
    )
