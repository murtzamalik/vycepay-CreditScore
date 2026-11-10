"""Unit tests for billing ORM models."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from app.models.billing import BillingRecord, BillingStatus, EmbedConfig


class TestBillingRecord:
    """Test BillingRecord model instantiation."""

    def test_create_billing_record(self) -> None:
        """Should create a BillingRecord with expected values."""
        record = BillingRecord(
            customer_id=uuid.uuid4(),
            billing_period="2026-03",
            status=BillingStatus.DRAFT,
            lite_queries=1000,
            pro_queries=500,
            batch_queries=50,
            total_queries=1550,
            base_fee=Decimal("50000.00"),
            lite_cost=Decimal("3000.00"),
            pro_cost=Decimal("7500.00"),
            overage_cost=Decimal("0.00"),
            total_amount=Decimal("50000.00"),
            currency="KES",
            included_queries=10000,
            overage_queries=0,
        )
        assert record.status == BillingStatus.DRAFT
        assert record.currency == "KES"
        assert record.billing_period == "2026-03"
        assert record.total_amount == Decimal("50000.00")

    def test_billing_status_values(self) -> None:
        """Verify all billing status enum values."""
        assert BillingStatus.DRAFT.value == "DRAFT"
        assert BillingStatus.FINALIZED.value == "FINALIZED"
        assert BillingStatus.PAID.value == "PAID"
        assert BillingStatus.OVERDUE.value == "OVERDUE"

    def test_repr(self) -> None:
        cid = uuid.uuid4()
        record = BillingRecord(
            customer_id=cid,
            billing_period="2026-03",
            total_amount=Decimal("50000.00"),
        )
        repr_str = repr(record)
        assert "BillingRecord" in repr_str
        assert "2026-03" in repr_str


class TestEmbedConfig:
    """Test EmbedConfig model instantiation."""

    def test_create_embed_config(self) -> None:
        config = EmbedConfig(
            customer_id=uuid.uuid4(),
            customer_token="test_token_abc123",
            allowed_origins=["https://example.com"],
            theme_config={"primaryColor": "#ff0000"},
            widget_config={"showNiqScore": True},
            is_active=True,
        )
        assert config.is_active is True
        assert config.customer_token == "test_token_abc123"
        assert config.allowed_origins == ["https://example.com"]

    def test_repr(self) -> None:
        cid = uuid.uuid4()
        config = EmbedConfig(
            customer_id=cid,
            customer_token="test",
        )
        repr_str = repr(config)
        assert "EmbedConfig" in repr_str
