"""Tests for Phase 7 — Customer & User Management Admin APIs.

Covers:
  - Customer onboarding (POST /v1/admin/customers)
  - Customer listing with filters (GET /v1/admin/customers)
  - License update (PUT /v1/admin/customers/{id}/license)
  - Customer activation (POST /v1/admin/customers/{id}/activate)
  - Usage tracking (GET /v1/admin/customers/{id}/usage)
  - User creation (POST /v1/admin/users)
  - User update/deactivation (PUT /v1/admin/users/{id})
  - Quota enforcement error format (Task 7.9)
  - RBAC enforcement
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import ForbiddenError, NotFoundError, VyceScoreError
from app.core.quota import (
    QuotaExceededError,
    QuotaResult,
    _next_period_reset,
    check_monthly_quota,
    enforce_monthly_quota,
)
from app.models.customer import Customer, CustomerStatus, LicenseTier
from app.models.user import User, UserRole
from app.schemas.admin import (
    CustomerCreateRequest,
    LicenseUpdateRequest,
    UserCreateRequest,
    UserUpdateRequest,
)
from app.services.auth_service import AuthService
from app.services.customer_service import CustomerService
from app.services.user_service import UserService


# -----------------------------------------------------------------------
# Test helpers
# -----------------------------------------------------------------------


def _make_customer(**overrides: object) -> MagicMock:
    """Create a mock Customer with sensible defaults."""
    defaults: dict[str, object] = {
        "customer_id": uuid.uuid4(),
        "name": "Test Bank Ltd",
        "license_tier": LicenseTier.LITE,
        "status": CustomerStatus.PENDING,
        "api_key_hash": "abc123hash",
        "monthly_query_limit": 10000,
        "sandbox_enabled": True,
        "production_enabled": False,
        "created_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    customer = MagicMock(spec=Customer)
    for k, v in defaults.items():
        setattr(customer, k, v)
    return customer


def _make_user(**overrides: object) -> MagicMock:
    """Create a mock User with sensible defaults."""
    defaults: dict[str, object] = {
        "user_id": uuid.uuid4(),
        "email": "admin@vycescore.com",
        "password_hash": AuthService.hash_password("TempPassword1"),
        "full_name": "Admin User",
        "role": UserRole.ADMIN,
        "is_active": True,
        "failed_login_attempts": 0,
        "locked_until": None,
        "last_login": None,
        "must_change_password": True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    user = MagicMock(spec=User)
    for k, v in defaults.items():
        setattr(user, k, v)
    return user


def _mock_db_returning(value: object) -> AsyncMock:
    """Return a mock AsyncSession whose execute() returns the given scalar."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = value
    mock_result.scalars.return_value.all.return_value = (
        [value] if value is not None else []
    )
    mock_result.scalar_one.return_value = 1 if value is not None else 0
    mock_result.all.return_value = []

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.flush = AsyncMock()
    mock_db.add = MagicMock()
    return mock_db


# -----------------------------------------------------------------------
# Task 7.1 — Customer creation
# -----------------------------------------------------------------------


class TestCustomerCreation:
    """POST /v1/admin/customers — onboard new customer."""

    @pytest.mark.asyncio
    async def test_create_customer_returns_api_key(self) -> None:
        db = _mock_db_returning(None)
        payload = CustomerCreateRequest(
            name="New Bank",
            contact_email="info@newbank.co.ke",
            license_tier=LicenseTier.PRO,
            monthly_query_limit=5000,
        )

        result = await CustomerService.create_customer(db, payload)

        assert result.api_key.startswith("vyc_")
        assert result.customer.name == "New Bank"
        assert result.customer.license_tier == LicenseTier.PRO
        assert result.customer.status == CustomerStatus.PENDING
        assert result.customer.sandbox_enabled is True
        assert result.customer.production_enabled is False
        assert result.customer.monthly_query_limit == 5000

    @pytest.mark.asyncio
    async def test_create_customer_adds_to_db(self) -> None:
        db = _mock_db_returning(None)
        payload = CustomerCreateRequest(
            name="Another Bank",
            contact_email="ops@another.co.ke",
            license_tier=LicenseTier.LITE,
            monthly_query_limit=1000,
        )

        await CustomerService.create_customer(db, payload)

        db.add.assert_called_once()
        db.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_customer_api_key_is_unique_per_call(self) -> None:
        payload = CustomerCreateRequest(
            name="Bank",
            contact_email="a@b.com",
            license_tier=LicenseTier.LITE,
            monthly_query_limit=100,
        )
        db1 = _mock_db_returning(None)
        db2 = _mock_db_returning(None)

        r1 = await CustomerService.create_customer(db1, payload)
        r2 = await CustomerService.create_customer(db2, payload)

        assert r1.api_key != r2.api_key


# -----------------------------------------------------------------------
# Task 7.2 — List customers
# -----------------------------------------------------------------------


class TestCustomerListing:
    """GET /v1/admin/customers — list with filters."""

    @pytest.mark.asyncio
    async def test_list_customers_returns_items_and_total(self) -> None:
        customer = _make_customer()

        # Build a mock that handles multiple execute() calls
        call_count = 0
        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                # Count query
                result.scalar_one.return_value = 1
            else:
                # Data query
                result.scalars.return_value.all.return_value = [customer]
            return result

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=mock_execute)

        items, total = await CustomerService.list_customers(db)

        assert total == 1
        assert len(items) == 1
        assert items[0].name == customer.name

    @pytest.mark.asyncio
    async def test_list_customers_empty(self) -> None:
        call_count = 0
        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalar_one.return_value = 0
            else:
                result.scalars.return_value.all.return_value = []
            return result

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=mock_execute)

        items, total = await CustomerService.list_customers(db)

        assert total == 0
        assert len(items) == 0


# -----------------------------------------------------------------------
# Task 7.3 — License update
# -----------------------------------------------------------------------


class TestLicenseUpdate:
    """PUT /v1/admin/customers/{id}/license."""

    @pytest.mark.asyncio
    async def test_update_tier(self) -> None:
        customer = _make_customer(license_tier=LicenseTier.LITE)
        db = _mock_db_returning(customer)
        payload = LicenseUpdateRequest(tier=LicenseTier.PRO)

        result = await CustomerService.update_license(
            db, customer.customer_id, payload,
        )

        assert customer.license_tier == LicenseTier.PRO

    @pytest.mark.asyncio
    async def test_update_query_limit(self) -> None:
        customer = _make_customer(monthly_query_limit=1000)
        db = _mock_db_returning(customer)
        payload = LicenseUpdateRequest(queryLimit=5000)

        result = await CustomerService.update_license(
            db, customer.customer_id, payload,
        )

        assert customer.monthly_query_limit == 5000

    @pytest.mark.asyncio
    async def test_update_license_not_found(self) -> None:
        db = _mock_db_returning(None)
        payload = LicenseUpdateRequest(tier=LicenseTier.PRO)

        with pytest.raises(NotFoundError, match="Customer"):
            await CustomerService.update_license(db, uuid.uuid4(), payload)


# -----------------------------------------------------------------------
# Task 7.4 — Customer activation
# -----------------------------------------------------------------------


class TestCustomerActivation:
    """POST /v1/admin/customers/{id}/activate."""

    @pytest.mark.asyncio
    async def test_activate_customer_with_logs(self) -> None:
        customer = _make_customer()

        call_count = 0
        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                # Customer lookup
                result.scalar_one_or_none.return_value = customer
            else:
                # Log count query
                result.scalar_one.return_value = 5
            return result

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=mock_execute)
        db.flush = AsyncMock()

        result = await CustomerService.activate_customer(db, customer.customer_id)

        assert customer.production_enabled is True
        assert customer.status == CustomerStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_activate_customer_without_logs_raises(self) -> None:
        customer = _make_customer()

        call_count = 0
        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalar_one_or_none.return_value = customer
            else:
                result.scalar_one.return_value = 0
            return result

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=mock_execute)

        with pytest.raises(ForbiddenError, match="sandbox testing"):
            await CustomerService.activate_customer(db, customer.customer_id)

    @pytest.mark.asyncio
    async def test_activate_customer_not_found(self) -> None:
        db = _mock_db_returning(None)

        with pytest.raises(NotFoundError, match="Customer"):
            await CustomerService.activate_customer(db, uuid.uuid4())


# -----------------------------------------------------------------------
# Task 7.6 — User creation
# -----------------------------------------------------------------------


class TestUserCreation:
    """POST /v1/admin/users — create admin user."""

    @pytest.mark.asyncio
    async def test_create_user_returns_temp_password(self) -> None:
        db = _mock_db_returning(None)
        payload = UserCreateRequest(
            email="newuser@vycescore.com",
            full_name="New User",
            role=UserRole.OPERATOR,
        )

        result = await UserService.create_user(db, payload)

        assert result.temporary_password
        assert len(result.temporary_password) > 8
        assert result.user.email == "newuser@vycescore.com"
        assert result.user.full_name == "New User"
        assert result.user.role == UserRole.OPERATOR
        assert result.user.must_change_password is True
        assert result.user.is_active is True

    @pytest.mark.asyncio
    async def test_create_user_adds_to_db(self) -> None:
        db = _mock_db_returning(None)
        payload = UserCreateRequest(
            email="newuser2@vycescore.com",
            full_name="New User 2",
            role=UserRole.READ_ONLY,
        )

        await UserService.create_user(db, payload)

        db.add.assert_called_once()
        db.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_user_duplicate_email_raises(self) -> None:
        existing_user = _make_user(email="dup@vycescore.com")
        db = _mock_db_returning(existing_user)
        payload = UserCreateRequest(
            email="dup@vycescore.com",
            full_name="Duplicate User",
            role=UserRole.OPERATOR,
        )

        with pytest.raises(VyceScoreError, match="already exists"):
            await UserService.create_user(db, payload)


# -----------------------------------------------------------------------
# Task 7.7 — User update/deactivation
# -----------------------------------------------------------------------


class TestUserUpdate:
    """PUT /v1/admin/users/{id}."""

    @pytest.mark.asyncio
    async def test_update_user_role(self) -> None:
        user = _make_user(role=UserRole.OPERATOR)
        db = _mock_db_returning(user)
        payload = UserUpdateRequest(role=UserRole.ADMIN)

        result = await UserService.update_user(db, user.user_id, payload)

        assert user.role == UserRole.ADMIN

    @pytest.mark.asyncio
    async def test_deactivate_user(self) -> None:
        user = _make_user(is_active=True)
        db = _mock_db_returning(user)
        payload = UserUpdateRequest(is_active=False)

        result = await UserService.update_user(db, user.user_id, payload)

        assert user.is_active is False

    @pytest.mark.asyncio
    async def test_reactivate_user(self) -> None:
        user = _make_user(is_active=False)
        db = _mock_db_returning(user)
        payload = UserUpdateRequest(is_active=True)

        result = await UserService.update_user(db, user.user_id, payload)

        assert user.is_active is True

    @pytest.mark.asyncio
    async def test_update_user_not_found(self) -> None:
        db = _mock_db_returning(None)
        payload = UserUpdateRequest(role=UserRole.READ_ONLY)

        with pytest.raises(NotFoundError, match="User"):
            await UserService.update_user(db, uuid.uuid4(), payload)


# -----------------------------------------------------------------------
# Task 7.8 — Usage tracking
# -----------------------------------------------------------------------


class TestUsageTracking:
    """GET /v1/admin/customers/{id}/usage."""

    @pytest.mark.asyncio
    async def test_get_usage_customer_not_found(self) -> None:
        # First call returns None for customer check
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(NotFoundError, match="Customer"):
            await CustomerService.get_usage(db, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_get_usage_returns_stats(self) -> None:
        customer_id = uuid.uuid4()

        call_count = 0
        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                # Customer existence check
                result.scalar_one_or_none.return_value = customer_id
            elif call_count == 2:
                # Total requests
                result.scalar_one.return_value = 150
            elif call_count == 3:
                # Successful requests
                result.scalar_one.return_value = 140
            elif call_count == 4:
                # Endpoint breakdown
                result.all.return_value = [
                    ("GET /v1/scores/lite/...", 100),
                    ("GET /v1/scores/pro/...", 50),
                ]
            return result

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=mock_execute)

        usage = await CustomerService.get_usage(db, customer_id, "2026-03")

        assert usage.customer_id == customer_id
        assert usage.period == "2026-03"
        assert usage.total_requests == 150
        assert usage.successful_requests == 140
        assert usage.failed_requests == 10
        assert usage.endpoints["GET /v1/scores/lite/..."] == 100


# -----------------------------------------------------------------------
# Task 7.9 — Quota enforcement error format
# -----------------------------------------------------------------------


class TestQuotaEnforcement:
    """Quota exceeded error follows §9.8 format."""

    def test_quota_exceeded_error_format(self) -> None:
        err = QuotaExceededError(quota=10000, used=10000, resets_at="2026-04-01T00:00:00Z")

        assert err.code == "RATE_LIMIT_EXCEEDED"
        assert "Monthly query quota exceeded" in err.message
        assert err.details["quota"] == 10000
        assert err.details["used"] == 10000
        assert err.details["resetsAt"] == "2026-04-01T00:00:00Z"
        assert err.status_code == 429

    def test_next_period_reset_regular_month(self) -> None:
        assert _next_period_reset("2026-03") == "2026-04-01T00:00:00Z"

    def test_next_period_reset_december(self) -> None:
        assert _next_period_reset("2026-12") == "2027-01-01T00:00:00Z"

    @pytest.mark.asyncio
    async def test_enforce_monthly_quota_raises_on_exceeded(self) -> None:
        redis = AsyncMock()
        redis.get = AsyncMock(return_value="10000")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = 10000

        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(QuotaExceededError) as exc_info:
            await enforce_monthly_quota(redis, db, str(uuid.uuid4()))

        assert exc_info.value.details["quota"] == 10000
        assert exc_info.value.details["used"] == 10000

    @pytest.mark.asyncio
    async def test_enforce_monthly_quota_allows_when_under_limit(self) -> None:
        redis = AsyncMock()
        redis.get = AsyncMock(return_value="500")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = 10000

        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)

        result = await enforce_monthly_quota(redis, db, str(uuid.uuid4()))

        assert result.allowed is True
        assert result.remaining == 9500


# -----------------------------------------------------------------------
# RBAC enforcement tests
# -----------------------------------------------------------------------


class TestRBACEnforcement:
    """Verify RBAC checks in admin endpoints."""

    def test_admin_role_passes_require_admin(self) -> None:
        from app.api.v1.endpoints.admin import _require_admin

        user = _make_user(role=UserRole.ADMIN)
        # Should not raise
        _require_admin(user)

    def test_operator_role_fails_require_admin(self) -> None:
        from app.api.v1.endpoints.admin import _require_admin

        user = _make_user(role=UserRole.OPERATOR)
        with pytest.raises(ForbiddenError, match="Admin role required"):
            _require_admin(user)

    def test_partner_role_fails_require_admin(self) -> None:
        from app.api.v1.endpoints.admin import _require_admin

        user = _make_user(role=UserRole.PARTNER)
        with pytest.raises(ForbiddenError, match="Admin role required"):
            _require_admin(user)

    def test_readonly_role_fails_require_admin(self) -> None:
        from app.api.v1.endpoints.admin import _require_admin

        user = _make_user(role=UserRole.READ_ONLY)
        with pytest.raises(ForbiddenError, match="Admin role required"):
            _require_admin(user)

    def test_admin_passes_require_admin_or_operator(self) -> None:
        from app.api.v1.endpoints.admin import _require_admin_or_operator

        user = _make_user(role=UserRole.ADMIN)
        _require_admin_or_operator(user)

    def test_operator_passes_require_admin_or_operator(self) -> None:
        from app.api.v1.endpoints.admin import _require_admin_or_operator

        user = _make_user(role=UserRole.OPERATOR)
        _require_admin_or_operator(user)

    def test_partner_fails_require_admin_or_operator(self) -> None:
        from app.api.v1.endpoints.admin import _require_admin_or_operator

        user = _make_user(role=UserRole.PARTNER)
        with pytest.raises(ForbiddenError):
            _require_admin_or_operator(user)

    def test_readonly_fails_require_admin_or_operator(self) -> None:
        from app.api.v1.endpoints.admin import _require_admin_or_operator

        user = _make_user(role=UserRole.READ_ONLY)
        with pytest.raises(ForbiddenError):
            _require_admin_or_operator(user)


# -----------------------------------------------------------------------
# Schema validation tests
# -----------------------------------------------------------------------


class TestSchemaValidation:
    """Verify Pydantic schema validation rules."""

    def test_customer_create_requires_positive_limit(self) -> None:
        with pytest.raises(Exception):
            CustomerCreateRequest(
                name="Bank",
                contact_email="a@b.com",
                license_tier=LicenseTier.LITE,
                monthly_query_limit=0,
            )

    def test_customer_create_requires_name(self) -> None:
        with pytest.raises(Exception):
            CustomerCreateRequest(
                name="",
                contact_email="a@b.com",
                license_tier=LicenseTier.LITE,
                monthly_query_limit=100,
            )

    def test_customer_create_valid_email(self) -> None:
        with pytest.raises(Exception):
            CustomerCreateRequest(
                name="Bank",
                contact_email="not-an-email",
                license_tier=LicenseTier.LITE,
                monthly_query_limit=100,
            )

    def test_user_create_requires_valid_role(self) -> None:
        req = UserCreateRequest(
            email="user@vycescore.com",
            full_name="User",
            role=UserRole.ADMIN,
        )
        assert req.role == UserRole.ADMIN

    def test_license_update_accepts_alias(self) -> None:
        req = LicenseUpdateRequest(queryLimit=5000)
        assert req.query_limit == 5000

    def test_user_update_partial(self) -> None:
        req = UserUpdateRequest(is_active=False)
        assert req.is_active is False
        assert req.role is None
