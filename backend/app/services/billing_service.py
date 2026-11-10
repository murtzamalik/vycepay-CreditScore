"""Billing calculation service (BRD §7.3.2).

Pricing tiers:
  - Lite:      KES 50,000/mo base, 10,000 queries included, KES 3/query overage
  - Pro:       KES 150,000/mo base, 5,000 queries included, KES 15/query overage
  - Deep Dive: Custom enterprise pricing (stored on customer record)

Lite queries cost KES 3 each; Pro queries cost KES 15 each.
Overage is charged when total_queries > included_queries for the tier.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import and_, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.models.api_request_log import ApiRequestLog
from app.models.billing import BillingRecord, BillingStatus
from app.models.customer import Customer, LicenseTier

logger = get_logger("billing_service")

# ---------------------------------------------------------------------------
# Pricing configuration (per BRD §7.3.2)
# ---------------------------------------------------------------------------

TIER_PRICING: dict[LicenseTier, dict[str, Decimal | int]] = {
    LicenseTier.LITE: {
        "base_fee": Decimal("50000.00"),
        "included_queries": 10000,
        "per_lite_query": Decimal("3.00"),
        "per_pro_query": Decimal("15.00"),
        "overage_rate": Decimal("3.00"),
    },
    LicenseTier.PRO: {
        "base_fee": Decimal("150000.00"),
        "included_queries": 5000,
        "per_lite_query": Decimal("3.00"),
        "per_pro_query": Decimal("15.00"),
        "overage_rate": Decimal("15.00"),
    },
    LicenseTier.DEEP_DIVE: {
        "base_fee": Decimal("500000.00"),
        "included_queries": 20000,
        "per_lite_query": Decimal("3.00"),
        "per_pro_query": Decimal("15.00"),
        "overage_rate": Decimal("10.00"),
    },
}


class BillingService:
    """Service for calculating and managing billing records."""

    @staticmethod
    async def get_monthly_query_counts(
        db: AsyncSession,
        customer_id: str,
        year: int,
        month: int,
    ) -> dict[str, int]:
        """Count queries by type for a given customer and month.

        Returns dict with lite_queries, pro_queries, batch_queries, total_queries.
        """
        # Count lite queries
        lite_count = await db.scalar(
            select(func.count(ApiRequestLog.log_id)).where(
                and_(
                    ApiRequestLog.customer_id == customer_id,
                    extract("year", ApiRequestLog.request_time) == year,
                    extract("month", ApiRequestLog.request_time) == month,
                    ApiRequestLog.endpoint.like("%/lite/%"),
                )
            )
        ) or 0

        # Count pro queries
        pro_count = await db.scalar(
            select(func.count(ApiRequestLog.log_id)).where(
                and_(
                    ApiRequestLog.customer_id == customer_id,
                    extract("year", ApiRequestLog.request_time) == year,
                    extract("month", ApiRequestLog.request_time) == month,
                    ApiRequestLog.endpoint.like("%/pro/%"),
                )
            )
        ) or 0

        # Count batch queries
        batch_count = await db.scalar(
            select(func.count(ApiRequestLog.log_id)).where(
                and_(
                    ApiRequestLog.customer_id == customer_id,
                    extract("year", ApiRequestLog.request_time) == year,
                    extract("month", ApiRequestLog.request_time) == month,
                    ApiRequestLog.endpoint.like("%/batch%"),
                )
            )
        ) or 0

        total = lite_count + pro_count + batch_count

        return {
            "lite_queries": lite_count,
            "pro_queries": pro_count,
            "batch_queries": batch_count,
            "total_queries": total,
        }

    @staticmethod
    async def get_daily_breakdown(
        db: AsyncSession,
        customer_id: str,
        year: int,
        month: int,
    ) -> list[dict[str, int | str]]:
        """Get daily query breakdown for a customer in a specific month."""
        rows = await db.execute(
            select(
                func.date(ApiRequestLog.request_time).label("day"),
                func.count(ApiRequestLog.log_id).filter(
                    ApiRequestLog.endpoint.like("%/lite/%")
                ).label("lite_queries"),
                func.count(ApiRequestLog.log_id).filter(
                    ApiRequestLog.endpoint.like("%/pro/%")
                ).label("pro_queries"),
                func.count(ApiRequestLog.log_id).filter(
                    ApiRequestLog.endpoint.like("%/batch%")
                ).label("batch_queries"),
                func.count(ApiRequestLog.log_id).label("total_queries"),
            )
            .where(
                and_(
                    ApiRequestLog.customer_id == customer_id,
                    extract("year", ApiRequestLog.request_time) == year,
                    extract("month", ApiRequestLog.request_time) == month,
                )
            )
            .group_by(func.date(ApiRequestLog.request_time))
            .order_by(func.date(ApiRequestLog.request_time))
        )

        return [
            {
                "date": str(row.day),
                "lite_queries": row.lite_queries or 0,
                "pro_queries": row.pro_queries or 0,
                "batch_queries": row.batch_queries or 0,
                "total_queries": row.total_queries or 0,
            }
            for row in rows.all()
        ]

    @staticmethod
    def calculate_charges(
        tier: LicenseTier,
        lite_queries: int,
        pro_queries: int,
        batch_queries: int,
    ) -> dict[str, Decimal | int]:
        """Calculate billing charges for given query counts and tier.

        Returns dict with base_fee, lite_cost, pro_cost, overage_cost,
        total_amount, included_queries, overage_queries.
        """
        pricing = TIER_PRICING[tier]
        base_fee = Decimal(str(pricing["base_fee"]))
        included = int(pricing["included_queries"])
        overage_rate = Decimal(str(pricing["overage_rate"]))
        per_lite = Decimal(str(pricing["per_lite_query"]))
        per_pro = Decimal(str(pricing["per_pro_query"]))

        lite_cost = Decimal(lite_queries) * per_lite
        pro_cost = Decimal(pro_queries) * per_pro

        total_queries = lite_queries + pro_queries + batch_queries
        overage_queries = max(0, total_queries - included)
        overage_cost = Decimal(overage_queries) * overage_rate

        total_amount = base_fee + overage_cost

        return {
            "base_fee": base_fee,
            "lite_cost": lite_cost,
            "pro_cost": pro_cost,
            "overage_cost": overage_cost,
            "total_amount": total_amount,
            "included_queries": included,
            "overage_queries": overage_queries,
        }

    @staticmethod
    async def generate_billing_record(
        db: AsyncSession,
        customer_id: str,
        billing_period: str,
    ) -> BillingRecord:
        """Generate or update a billing record for a customer and period.

        Args:
            customer_id: UUID of the customer.
            billing_period: YYYY-MM format string.

        Returns:
            The created or updated BillingRecord.

        Raises:
            NotFoundError: If the customer does not exist.
        """
        # Fetch customer
        result = await db.execute(
            select(Customer).where(Customer.customer_id == customer_id)
        )
        customer = result.scalar_one_or_none()
        if customer is None:
            raise NotFoundError("Customer", customer_id)

        # Parse period
        year, month = int(billing_period[:4]), int(billing_period[5:7])

        # Get query counts
        counts = await BillingService.get_monthly_query_counts(
            db, customer_id, year, month,
        )

        # Calculate charges
        charges = BillingService.calculate_charges(
            tier=customer.license_tier,
            lite_queries=counts["lite_queries"],
            pro_queries=counts["pro_queries"],
            batch_queries=counts["batch_queries"],
        )

        # Check for existing record
        existing = await db.execute(
            select(BillingRecord).where(
                and_(
                    BillingRecord.customer_id == customer_id,
                    BillingRecord.billing_period == billing_period,
                )
            )
        )
        record = existing.scalar_one_or_none()

        if record is not None:
            # Update existing record
            record.lite_queries = counts["lite_queries"]
            record.pro_queries = counts["pro_queries"]
            record.batch_queries = counts["batch_queries"]
            record.total_queries = counts["total_queries"]
            record.base_fee = charges["base_fee"]
            record.lite_cost = charges["lite_cost"]
            record.pro_cost = charges["pro_cost"]
            record.overage_cost = charges["overage_cost"]
            record.total_amount = charges["total_amount"]
            record.included_queries = charges["included_queries"]
            record.overage_queries = charges["overage_queries"]
        else:
            record = BillingRecord(
                customer_id=customer_id,
                billing_period=billing_period,
                lite_queries=counts["lite_queries"],
                pro_queries=counts["pro_queries"],
                batch_queries=counts["batch_queries"],
                total_queries=counts["total_queries"],
                base_fee=charges["base_fee"],
                lite_cost=charges["lite_cost"],
                pro_cost=charges["pro_cost"],
                overage_cost=charges["overage_cost"],
                total_amount=charges["total_amount"],
                included_queries=charges["included_queries"],
                overage_queries=charges["overage_queries"],
            )
            db.add(record)

        await db.flush()
        await logger.ainfo(
            "billing.record_generated",
            customer_id=customer_id,
            period=billing_period,
            total_amount=str(record.total_amount),
        )
        return record

    @staticmethod
    async def get_billing_record(
        db: AsyncSession,
        customer_id: str,
        billing_period: str,
    ) -> BillingRecord | None:
        """Retrieve an existing billing record."""
        result = await db.execute(
            select(BillingRecord).where(
                and_(
                    BillingRecord.customer_id == customer_id,
                    BillingRecord.billing_period == billing_period,
                )
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_customer_billing_history(
        db: AsyncSession,
        customer_id: str,
        limit: int = 12,
    ) -> list[BillingRecord]:
        """Get billing history for a customer, most recent first."""
        result = await db.execute(
            select(BillingRecord)
            .where(BillingRecord.customer_id == customer_id)
            .order_by(BillingRecord.billing_period.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
