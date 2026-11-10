"""Customer management business logic (Phase 7 — Tasks 7.1–7.5, 7.8)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError, VyceScoreError
from app.core.logging import get_logger
from app.models.api_request_log import ApiRequestLog
from app.models.customer import Customer, CustomerStatus, LicenseTier
from app.schemas.admin import (
    CustomerCreateRequest,
    CustomerCreateResponse,
    CustomerResponse,
    LicenseUpdateRequest,
    UsageResponse,
)
from app.services.auth_service import AuthService

logger = get_logger("customer_service")


class CustomerService:
    """Service layer for customer lifecycle management."""

    # ------------------------------------------------------------------
    # Task 7.1 — Onboard new customer
    # ------------------------------------------------------------------

    @staticmethod
    async def create_customer(
        db: AsyncSession,
        payload: CustomerCreateRequest,
    ) -> CustomerCreateResponse:
        """Create a new customer with PENDING status and generate an API key.

        The plaintext API key is returned exactly once; only the SHA-256
        hash is persisted.
        """
        raw_key, key_hash = AuthService.generate_api_key()

        now = datetime.now(timezone.utc)
        customer = Customer(
            customer_id=uuid.uuid4(),
            name=payload.name,
            contact_email=payload.contact_email,
            license_tier=payload.license_tier,
            status=CustomerStatus.PENDING,
            api_key_hash=key_hash,
            monthly_query_limit=payload.monthly_query_limit,
            sandbox_enabled=True,
            production_enabled=False,
            created_at=now,
        )
        db.add(customer)
        await db.flush()

        await logger.ainfo(
            "customer.created",
            customer_id=str(customer.customer_id),
            tier=customer.license_tier.value,
        )

        customer_resp = CustomerResponse(
            customer_id=customer.customer_id,
            name=customer.name,
            contact_email=customer.contact_email,
            license_tier=customer.license_tier,
            status=customer.status,
            monthly_query_limit=customer.monthly_query_limit,
            sandbox_enabled=customer.sandbox_enabled,
            production_enabled=customer.production_enabled,
            created_at=customer.created_at,
        )

        return CustomerCreateResponse(customer=customer_resp, api_key=raw_key)

    # ------------------------------------------------------------------
    # Task 7.2 — List customers with filtering and pagination
    # ------------------------------------------------------------------

    @staticmethod
    async def list_customers(
        db: AsyncSession,
        *,
        status: CustomerStatus | None = None,
        tier: LicenseTier | None = None,
        page: int = 1,
        limit: int = 50,
    ) -> tuple[list[CustomerResponse], int]:
        """Return a paginated, optionally filtered list of customers.

        Returns:
            Tuple of (customer list, total count).
        """
        query: Select[tuple[Customer]] = select(Customer)
        count_query = select(func.count()).select_from(Customer)

        if status is not None:
            query = query.where(Customer.status == status)
            count_query = count_query.where(Customer.status == status)
        if tier is not None:
            query = query.where(Customer.license_tier == tier)
            count_query = count_query.where(Customer.license_tier == tier)

        # Total count
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()

        # Paginate
        offset = (page - 1) * limit
        query = query.order_by(Customer.created_at.desc()).offset(offset).limit(limit)
        result = await db.execute(query)
        customers = result.scalars().all()

        items = [
            CustomerResponse(
                customer_id=c.customer_id,
                name=c.name,
                license_tier=c.license_tier,
                status=c.status,
                monthly_query_limit=c.monthly_query_limit,
                sandbox_enabled=c.sandbox_enabled,
                production_enabled=c.production_enabled,
                created_at=c.created_at,
            )
            for c in customers
        ]
        return items, total

    # ------------------------------------------------------------------
    # Task 7.3 — Update customer license
    # ------------------------------------------------------------------

    @staticmethod
    async def update_license(
        db: AsyncSession,
        customer_id: uuid.UUID,
        payload: LicenseUpdateRequest,
    ) -> CustomerResponse:
        """Update the license tier and/or query limit for a customer."""
        result = await db.execute(
            select(Customer).where(Customer.customer_id == customer_id)
        )
        customer = result.scalar_one_or_none()
        if customer is None:
            raise NotFoundError("Customer", str(customer_id))

        if payload.tier is not None:
            customer.license_tier = payload.tier
        if payload.query_limit is not None:
            customer.monthly_query_limit = payload.query_limit

        await db.flush()

        await logger.ainfo(
            "customer.license_updated",
            customer_id=str(customer_id),
            tier=customer.license_tier.value,
            query_limit=customer.monthly_query_limit,
        )

        return CustomerResponse(
            customer_id=customer.customer_id,
            name=customer.name,
            license_tier=customer.license_tier,
            status=customer.status,
            monthly_query_limit=customer.monthly_query_limit,
            sandbox_enabled=customer.sandbox_enabled,
            production_enabled=customer.production_enabled,
            created_at=customer.created_at,
        )

    # ------------------------------------------------------------------
    # Task 7.4 — Activate customer (sandbox → production)
    # ------------------------------------------------------------------

    @staticmethod
    async def activate_customer(
        db: AsyncSession,
        customer_id: uuid.UUID,
    ) -> CustomerResponse:
        """Activate a customer for production after verifying sandbox usage.

        Raises:
            NotFoundError: Customer does not exist.
            ForbiddenError: Customer has not completed sandbox testing.
        """
        result = await db.execute(
            select(Customer).where(Customer.customer_id == customer_id)
        )
        customer = result.scalar_one_or_none()
        if customer is None:
            raise NotFoundError("Customer", str(customer_id))

        # Validate sandbox testing — check for at least one API request log
        log_result = await db.execute(
            select(func.count()).select_from(ApiRequestLog).where(
                ApiRequestLog.customer_id == customer_id
            )
        )
        log_count = log_result.scalar_one()

        if log_count == 0:
            raise ForbiddenError(
                "Customer must complete sandbox testing before activation. "
                "No API request logs found."
            )

        customer.production_enabled = True
        customer.status = CustomerStatus.ACTIVE
        await db.flush()

        await logger.ainfo(
            "customer.activated",
            customer_id=str(customer_id),
        )

        return CustomerResponse(
            customer_id=customer.customer_id,
            name=customer.name,
            license_tier=customer.license_tier,
            status=customer.status,
            monthly_query_limit=customer.monthly_query_limit,
            sandbox_enabled=customer.sandbox_enabled,
            production_enabled=customer.production_enabled,
            created_at=customer.created_at,
        )

    # ------------------------------------------------------------------
    # Task 7.8 — Usage tracking
    # ------------------------------------------------------------------

    @staticmethod
    async def get_usage(
        db: AsyncSession,
        customer_id: uuid.UUID,
        period: str | None = None,
    ) -> UsageResponse:
        """Query API usage for a customer in a given month.

        Args:
            period: YYYY-MM string. Defaults to current month.
        """
        # Verify customer exists
        cust_result = await db.execute(
            select(Customer.customer_id).where(Customer.customer_id == customer_id)
        )
        if cust_result.scalar_one_or_none() is None:
            raise NotFoundError("Customer", str(customer_id))

        if period is None:
            period = datetime.now(timezone.utc).strftime("%Y-%m")

        # Parse period boundaries
        year, month = int(period.split("-")[0]), int(period.split("-")[1])
        start = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end = datetime(year, month + 1, 1, tzinfo=timezone.utc)

        base_filter = (
            (ApiRequestLog.customer_id == customer_id)
            & (ApiRequestLog.request_time >= start)
            & (ApiRequestLog.request_time < end)
        )

        # Total requests
        total_result = await db.execute(
            select(func.count()).select_from(ApiRequestLog).where(base_filter)
        )
        total_requests = total_result.scalar_one()

        # Successful (2xx)
        success_result = await db.execute(
            select(func.count()).select_from(ApiRequestLog).where(
                base_filter,
                ApiRequestLog.response_status < 400,
            )
        )
        successful_requests = success_result.scalar_one()

        # Per-endpoint breakdown
        endpoint_result = await db.execute(
            select(ApiRequestLog.endpoint, func.count())
            .where(base_filter)
            .group_by(ApiRequestLog.endpoint)
        )
        endpoints = {row[0]: row[1] for row in endpoint_result.all()}

        return UsageResponse(
            customer_id=customer_id,
            period=period,
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=total_requests - successful_requests,
            endpoints=endpoints,
        )
