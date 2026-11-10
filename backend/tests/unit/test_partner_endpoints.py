"""Unit tests for partner and billing endpoint schemas and validation."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.billing import (
    ApiKeyInfoResponse,
    ApiKeyRotateResponse,
    ApiKeyRevokeResponse,
    BillingRecordResponse,
    BillingSummaryResponse,
    DailyUsageEntry,
    EmbedConfigRequest,
    EmbedConfigResponse,
    MonthlyStatementResponse,
    PartnerUsageResponse,
    PartnerUsageTrendResponse,
    PublicEmbedConfigResponse,
    UsageTrendEntry,
)


class TestDailyUsageEntry:
    """Test DailyUsageEntry schema."""

    def test_valid_entry(self) -> None:
        entry = DailyUsageEntry(
            date="2026-03-01",
            lite_queries=100,
            pro_queries=50,
            batch_queries=10,
            total_queries=160,
        )
        assert entry.date == "2026-03-01"
        assert entry.total_queries == 160

    def test_defaults(self) -> None:
        entry = DailyUsageEntry(date="2026-03-01")
        assert entry.lite_queries == 0
        assert entry.pro_queries == 0
        assert entry.batch_queries == 0
        assert entry.total_queries == 0


class TestPartnerUsageResponse:
    """Test PartnerUsageResponse schema."""

    def test_valid_response(self) -> None:
        resp = PartnerUsageResponse(
            customer_id="abc-123",
            customer_name="Test Bank",
            tier="LITE",
            billing_period="2026-03",
            total_queries=5000,
            lite_queries=4000,
            pro_queries=1000,
            batch_queries=0,
            query_limit=10000,
            queries_remaining=5000,
            usage_percentage=50.0,
            daily_usage=[],
        )
        assert resp.queries_remaining == 5000
        assert resp.usage_percentage == 50.0


class TestBillingRecordResponse:
    """Test BillingRecordResponse schema."""

    def test_valid_record(self) -> None:
        now = datetime.now(timezone.utc)
        resp = BillingRecordResponse(
            billing_id="test-id",
            customer_id="cust-id",
            billing_period="2026-03",
            status="DRAFT",
            lite_queries=1000,
            pro_queries=500,
            batch_queries=100,
            total_queries=1600,
            base_fee=Decimal("50000"),
            lite_cost=Decimal("3000"),
            pro_cost=Decimal("7500"),
            overage_cost=Decimal("0"),
            total_amount=Decimal("50000"),
            currency="KES",
            included_queries=10000,
            overage_queries=0,
            created_at=now,
            updated_at=now,
        )
        assert resp.currency == "KES"
        assert resp.total_amount == Decimal("50000")


class TestEmbedConfigRequest:
    """Test EmbedConfigRequest schema."""

    def test_defaults(self) -> None:
        req = EmbedConfigRequest()
        assert req.allowed_origins == []
        assert req.theme_config is None
        assert req.widget_config is None

    def test_with_values(self) -> None:
        req = EmbedConfigRequest(
            allowed_origins=["https://example.com", "https://bank.co.ke"],
            theme_config={"primaryColor": "#ff0000"},
            widget_config={"showNiqScore": True},
        )
        assert len(req.allowed_origins) == 2
        assert req.theme_config["primaryColor"] == "#ff0000"


class TestApiKeySchemas:
    """Test API key management schemas."""

    def test_rotate_response(self) -> None:
        resp = ApiKeyRotateResponse(api_key="vyc_test123")
        assert resp.api_key == "vyc_test123"
        assert "securely" in resp.message.lower()

    def test_revoke_response(self) -> None:
        resp = ApiKeyRevokeResponse()
        assert "revoked" in resp.message.lower()

    def test_info_response(self) -> None:
        now = datetime.now(timezone.utc)
        resp = ApiKeyInfoResponse(
            key_prefix="vyc_abc1...",
            created_at=now,
            last_used_at=now,
        )
        assert resp.key_prefix.startswith("vyc_")


class TestMonthlyStatementResponse:
    """Test MonthlyStatementResponse schema."""

    def test_with_daily_breakdown(self) -> None:
        now = datetime.now(timezone.utc)
        statement = MonthlyStatementResponse(
            billing_period="2026-03",
            customer_name="Test Bank",
            customer_id="cust-123",
            tier="LITE",
            status="DRAFT",
            base_fee=Decimal("50000"),
            lite_queries=100,
            lite_cost=Decimal("300"),
            pro_queries=50,
            pro_cost=Decimal("750"),
            batch_queries=0,
            overage_queries=0,
            overage_cost=Decimal("0"),
            total_queries=150,
            included_queries=10000,
            total_amount=Decimal("50000"),
            currency="KES",
            daily_breakdown=[
                DailyUsageEntry(
                    date="2026-03-01",
                    lite_queries=50,
                    pro_queries=25,
                    total_queries=75,
                ),
                DailyUsageEntry(
                    date="2026-03-02",
                    lite_queries=50,
                    pro_queries=25,
                    total_queries=75,
                ),
            ],
            generated_at=now,
        )
        assert len(statement.daily_breakdown) == 2
        assert statement.total_amount == Decimal("50000")


class TestPublicEmbedConfigResponse:
    """Test PublicEmbedConfigResponse schema."""

    def test_valid(self) -> None:
        resp = PublicEmbedConfigResponse(
            customer_token="token123",
            allowed_origins=["https://example.com"],
            theme_config={"primaryColor": "#1976d2"},
            widget_config=None,
        )
        assert resp.customer_token == "token123"
