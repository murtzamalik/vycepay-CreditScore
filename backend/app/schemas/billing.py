"""Billing and embed configuration Pydantic v2 schemas (BRD §7.3.2, §7.2.7)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Billing schemas
# ---------------------------------------------------------------------------


class BillingRecordResponse(BaseModel):
    """Billing record returned in API responses."""

    billing_id: str
    customer_id: str
    billing_period: str
    status: str
    lite_queries: int
    pro_queries: int
    batch_queries: int
    total_queries: int
    base_fee: Decimal
    lite_cost: Decimal
    pro_cost: Decimal
    overage_cost: Decimal
    total_amount: Decimal
    currency: str
    included_queries: int
    overage_queries: int
    created_at: datetime
    updated_at: datetime


class BillingSummaryResponse(BaseModel):
    """Summary billing info for partner usage pages."""

    billing_period: str
    total_queries: int
    lite_queries: int
    pro_queries: int
    batch_queries: int
    included_queries: int
    overage_queries: int
    total_amount: Decimal
    currency: str
    status: str


class MonthlyStatementResponse(BaseModel):
    """Detailed monthly billing statement."""

    billing_period: str
    customer_name: str
    customer_id: str
    tier: str
    status: str
    base_fee: Decimal
    lite_queries: int
    lite_cost: Decimal
    pro_queries: int
    pro_cost: Decimal
    batch_queries: int
    overage_queries: int
    overage_cost: Decimal
    total_queries: int
    included_queries: int
    total_amount: Decimal
    currency: str
    daily_breakdown: list[DailyUsageEntry]
    generated_at: datetime


class DailyUsageEntry(BaseModel):
    """Single day usage entry for billing statement."""

    date: str
    lite_queries: int = 0
    pro_queries: int = 0
    batch_queries: int = 0
    total_queries: int = 0


# Forward ref resolution
MonthlyStatementResponse.model_rebuild()


# ---------------------------------------------------------------------------
# Usage schemas
# ---------------------------------------------------------------------------


class PartnerUsageResponse(BaseModel):
    """Monthly usage statistics for authenticated partner."""

    customer_id: str
    customer_name: str
    tier: str
    billing_period: str
    total_queries: int
    lite_queries: int
    pro_queries: int
    batch_queries: int
    query_limit: int
    queries_remaining: int
    usage_percentage: float
    daily_usage: list[DailyUsageEntry]


class UsageTrendEntry(BaseModel):
    """Monthly usage trend entry."""

    period: str
    total_queries: int
    lite_queries: int
    pro_queries: int


class PartnerUsageTrendResponse(BaseModel):
    """Usage trend over multiple months."""

    customer_id: str
    months: list[UsageTrendEntry]


# ---------------------------------------------------------------------------
# API Key schemas
# ---------------------------------------------------------------------------


class ApiKeyRotateResponse(BaseModel):
    """Response after rotating API key — key is shown only once."""

    api_key: str
    message: str = "Store this key securely. It will not be shown again."


class ApiKeyInfoResponse(BaseModel):
    """Masked API key info for display."""

    key_prefix: str = Field(..., description="First 8 chars of the API key")
    created_at: datetime | None = None
    last_used_at: datetime | None = None


class ApiKeyRevokeResponse(BaseModel):
    """Response after revoking API key."""

    message: str = "API key has been revoked successfully."


# ---------------------------------------------------------------------------
# Embed config schemas
# ---------------------------------------------------------------------------


class EmbedConfigRequest(BaseModel):
    """Request body for creating/updating embed configuration."""

    allowed_origins: list[str] = Field(
        default_factory=list,
        description="List of allowed domains for iframe embedding",
    )
    theme_config: dict | None = Field(
        default=None,
        description="White-label theme settings (primaryColor, secondaryColor, logoUrl, appName)",
    )
    widget_config: dict | None = Field(
        default=None,
        description="Widget behavior configuration (showNiqScore, showRiskDrivers, etc.)",
    )


class EmbedConfigResponse(BaseModel):
    """Embed configuration returned in API responses."""

    embed_config_id: str
    customer_id: str
    customer_token: str
    allowed_origins: list[str]
    theme_config: dict | None
    widget_config: dict | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PublicEmbedConfigResponse(BaseModel):
    """Public embed config returned for widget initialization."""

    customer_token: str
    allowed_origins: list[str]
    theme_config: dict | None
    widget_config: dict | None
