"""Unit tests for the billing calculation service."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.models.customer import LicenseTier
from app.services.billing_service import BillingService, TIER_PRICING


class TestCalculateCharges:
    """Tests for BillingService.calculate_charges static method."""

    def test_lite_tier_within_included(self) -> None:
        """Lite tier: queries within included limit should have zero overage."""
        result = BillingService.calculate_charges(
            tier=LicenseTier.LITE,
            lite_queries=5000,
            pro_queries=0,
            batch_queries=0,
        )
        assert result["base_fee"] == Decimal("50000.00")
        assert result["overage_queries"] == 0
        assert result["overage_cost"] == Decimal("0.00")
        assert result["total_amount"] == Decimal("50000.00")
        assert result["included_queries"] == 10000
        assert result["lite_cost"] == Decimal("15000.00")  # 5000 * 3

    def test_lite_tier_with_overage(self) -> None:
        """Lite tier: queries above included limit incur overage charges."""
        result = BillingService.calculate_charges(
            tier=LicenseTier.LITE,
            lite_queries=12000,
            pro_queries=0,
            batch_queries=0,
        )
        assert result["overage_queries"] == 2000
        assert result["overage_cost"] == Decimal("6000.00")  # 2000 * 3
        assert result["total_amount"] == Decimal("56000.00")  # 50000 + 6000

    def test_pro_tier_within_included(self) -> None:
        """Pro tier: queries within included limit."""
        result = BillingService.calculate_charges(
            tier=LicenseTier.PRO,
            lite_queries=0,
            pro_queries=3000,
            batch_queries=0,
        )
        assert result["base_fee"] == Decimal("150000.00")
        assert result["overage_queries"] == 0
        assert result["total_amount"] == Decimal("150000.00")

    def test_pro_tier_with_overage(self) -> None:
        """Pro tier: overage at KES 15 per query."""
        result = BillingService.calculate_charges(
            tier=LicenseTier.PRO,
            lite_queries=2000,
            pro_queries=4000,
            batch_queries=0,
        )
        # total = 6000, included = 5000, overage = 1000
        assert result["overage_queries"] == 1000
        assert result["overage_cost"] == Decimal("15000.00")  # 1000 * 15
        assert result["total_amount"] == Decimal("165000.00")  # 150000 + 15000

    def test_deep_dive_tier(self) -> None:
        """Deep Dive tier: enterprise pricing."""
        result = BillingService.calculate_charges(
            tier=LicenseTier.DEEP_DIVE,
            lite_queries=5000,
            pro_queries=10000,
            batch_queries=3000,
        )
        # total = 18000, included = 20000, no overage
        assert result["overage_queries"] == 0
        assert result["base_fee"] == Decimal("500000.00")
        assert result["total_amount"] == Decimal("500000.00")

    def test_deep_dive_with_overage(self) -> None:
        """Deep Dive tier: overage at KES 10 per query."""
        result = BillingService.calculate_charges(
            tier=LicenseTier.DEEP_DIVE,
            lite_queries=10000,
            pro_queries=10000,
            batch_queries=5000,
        )
        # total = 25000, included = 20000, overage = 5000
        assert result["overage_queries"] == 5000
        assert result["overage_cost"] == Decimal("50000.00")  # 5000 * 10
        assert result["total_amount"] == Decimal("550000.00")

    def test_zero_queries(self) -> None:
        """Zero queries should still incur the base fee."""
        result = BillingService.calculate_charges(
            tier=LicenseTier.LITE,
            lite_queries=0,
            pro_queries=0,
            batch_queries=0,
        )
        assert result["total_amount"] == Decimal("50000.00")
        assert result["overage_queries"] == 0

    def test_mixed_queries_lite_tier(self) -> None:
        """Mixed Lite + Pro queries on Lite tier."""
        result = BillingService.calculate_charges(
            tier=LicenseTier.LITE,
            lite_queries=8000,
            pro_queries=1000,
            batch_queries=500,
        )
        # total = 9500, included = 10000, no overage
        assert result["overage_queries"] == 0
        assert result["lite_cost"] == Decimal("24000.00")  # 8000 * 3
        assert result["pro_cost"] == Decimal("15000.00")   # 1000 * 15

    def test_all_tiers_have_pricing(self) -> None:
        """Verify every LicenseTier has a pricing entry."""
        for tier in LicenseTier:
            assert tier in TIER_PRICING
            pricing = TIER_PRICING[tier]
            assert "base_fee" in pricing
            assert "included_queries" in pricing
            assert "overage_rate" in pricing
