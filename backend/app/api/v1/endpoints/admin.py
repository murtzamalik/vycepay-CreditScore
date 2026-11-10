"""Admin endpoints for customer and user management (Phase 7).

All endpoints require JWT authentication and appropriate RBAC permissions.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.dependencies import get_db
from app.models.customer import CustomerStatus, LicenseTier
from app.models.user import User, UserRole
from app.schemas.admin import (
    CustomerCreateRequest,
    CustomerCreateResponse,
    CustomerResponse,
    LicenseUpdateRequest,
    UsageResponse,
    UserCreateRequest,
    UserCreateResponse,
    UserResponse,
    UserUpdateRequest,
)
from app.schemas.common import PaginatedResponse
from app.services.customer_service import CustomerService
from app.services.user_service import UserService

router = APIRouter(prefix="/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# RBAC helpers
# ---------------------------------------------------------------------------


def _require_admin(user: User) -> None:
    """Raise 403 if the user is not an Admin."""
    if user.role != UserRole.ADMIN:
        from app.core.exceptions import ForbiddenError

        raise ForbiddenError("Admin role required for this operation")


def _require_admin_or_operator(user: User) -> None:
    """Raise 403 if the user is not an Admin or Operator."""
    if user.role not in (UserRole.ADMIN, UserRole.OPERATOR):
        from app.core.exceptions import ForbiddenError

        raise ForbiddenError("Admin or Operator role required for this operation")


# ---------------------------------------------------------------------------
# Task 7.1 — POST /v1/admin/customers
# ---------------------------------------------------------------------------


@router.post(
    "/customers",
    response_model=CustomerCreateResponse,
    status_code=201,
    summary="Onboard a new customer",
)
async def create_customer(
    body: CustomerCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CustomerCreateResponse:
    """Create a new customer with PENDING status and sandbox access.

    Returns the customer details and a plaintext API key (shown only once).
    Requires **Admin** role.
    """
    _require_admin(current_user)
    return await CustomerService.create_customer(db, body)


# ---------------------------------------------------------------------------
# Task 7.2 — GET /v1/admin/customers
# ---------------------------------------------------------------------------


@router.get(
    "/customers",
    response_model=PaginatedResponse[CustomerResponse],
    summary="List customers",
)
async def list_customers(
    status: CustomerStatus | None = Query(None, description="Filter by status"),
    tier: LicenseTier | None = Query(None, description="Filter by license tier"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=200, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[CustomerResponse]:
    """Return a paginated list of customers with optional filtering.

    Requires **Admin** or **Operator** role.
    """
    _require_admin_or_operator(current_user)

    items, total = await CustomerService.list_customers(
        db, status=status, tier=tier, page=page, limit=limit,
    )
    pages = (total + limit - 1) // limit if total > 0 else 0

    return PaginatedResponse[CustomerResponse](
        items=items,
        total=total,
        page=page,
        page_size=limit,
        pages=pages,
    )


# ---------------------------------------------------------------------------
# Task 7.3 — PUT /v1/admin/customers/{customerId}/license
# ---------------------------------------------------------------------------


@router.put(
    "/customers/{customer_id}/license",
    response_model=CustomerResponse,
    summary="Update customer license",
)
async def update_license(
    customer_id: uuid.UUID,
    body: LicenseUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CustomerResponse:
    """Update the license tier, query limit, or enabled features for a customer.

    Requires **Admin** role.
    """
    _require_admin(current_user)
    return await CustomerService.update_license(db, customer_id, body)


# ---------------------------------------------------------------------------
# Task 7.4 — POST /v1/admin/customers/{customerId}/activate
# ---------------------------------------------------------------------------


@router.post(
    "/customers/{customer_id}/activate",
    response_model=CustomerResponse,
    summary="Activate customer for production",
)
async def activate_customer(
    customer_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CustomerResponse:
    """Activate a customer for production access.

    Validates that the customer has completed sandbox testing (at least one
    API request log exists). Requires **Admin** role.
    """
    _require_admin(current_user)
    return await CustomerService.activate_customer(db, customer_id)


# ---------------------------------------------------------------------------
# Task 7.8 — GET /v1/admin/customers/{customerId}/usage
# ---------------------------------------------------------------------------


@router.get(
    "/customers/{customer_id}/usage",
    response_model=UsageResponse,
    summary="Get customer API usage",
)
async def get_usage(
    customer_id: uuid.UUID,
    period: str | None = Query(
        None,
        description="Month period as YYYY-MM. Defaults to current month.",
        pattern=r"^\d{4}-(?:0[1-9]|1[0-2])$",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UsageResponse:
    """Return API usage statistics for a customer in the specified month.

    Requires **Admin** or **Operator** role.
    """
    _require_admin_or_operator(current_user)
    return await CustomerService.get_usage(db, customer_id, period)


# ---------------------------------------------------------------------------
# Task 7.6 — POST /v1/admin/users
# ---------------------------------------------------------------------------


@router.post(
    "/users",
    response_model=UserCreateResponse,
    status_code=201,
    summary="Create admin user",
)
async def create_user(
    body: UserCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserCreateResponse:
    """Create a new admin portal user with a temporary password.

    The user must change their password on first login
    (``must_change_password=True``). Requires **Admin** role.
    """
    _require_admin(current_user)
    return await UserService.create_user(db, body)


# ---------------------------------------------------------------------------
# Task 7.7 — PUT /v1/admin/users/{userId}
# ---------------------------------------------------------------------------


@router.put(
    "/users/{user_id}",
    response_model=UserResponse,
    summary="Update or deactivate user",
)
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Update a user's role or active status.

    Deactivating a user (``is_active=false``) effectively revokes all
    sessions because JWT validation checks the ``is_active`` flag.
    Requires **Admin** role.
    """
    _require_admin(current_user)
    return await UserService.update_user(db, user_id, body)
