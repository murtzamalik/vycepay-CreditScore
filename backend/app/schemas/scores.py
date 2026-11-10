"""Score request/response schemas (BRD §9.2.1, §9.3.1, §4.3)."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared components
# ---------------------------------------------------------------------------


class ScoreMetadata(BaseModel):
    """Metadata about the scoring computation."""

    model_version: str = Field(..., description="ML model version used for scoring")
    feature_date: str = Field(..., description="Date of the feature snapshot (ISO 8601)")
    data_quality: str = Field(
        ...,
        description="Overall data quality indicator",
        pattern="^(high|medium|low)$",
    )


class ScoreInterpretation(BaseModel):
    """Score range interpretation (BRD §4.3)."""

    risk_level: str = Field(
        ...,
        description="Risk classification: Very Low Risk, Low Risk, Medium Risk, High Risk, Very High Risk",
    )
    interpretation: str = Field(
        ...,
        description="Human-readable creditworthiness assessment",
    )


class RiskDriverResponse(BaseModel):
    """A single SHAP-explained risk driver (BRD §9.3.1)."""

    factor: str = Field(..., description="Human-readable factor name")
    impact: str = Field(
        ...,
        description="Direction of impact on credit score",
        pattern="^(positive|negative)$",
    )
    description: str = Field(..., description="Human-readable explanation")
    contribution: int = Field(
        ...,
        ge=0,
        le=100,
        description="Contribution percentage to the overall score",
    )


class ConfidenceInterval(BaseModel):
    """Confidence interval bounds for the VyceScore."""

    lower: int = Field(..., ge=300, le=900, description="Lower bound of score estimate")
    upper: int = Field(..., ge=300, le=900, description="Upper bound of score estimate")


# ---------------------------------------------------------------------------
# Lite endpoint — BRD §9.2.1
# ---------------------------------------------------------------------------


class ScoreLiteResponse(BaseModel):
    """Response for GET /v1/scores/lite/{nationalId} (BRD §9.2.1)."""

    vyce_score: int = Field(..., ge=300, le=900, description="VyceScore credit score")
    niq_score: int = Field(..., ge=0, le=100, description="Network Interdependence & Quality score")
    score_date: str = Field(..., description="Date the score was computed (ISO 8601)")
    score_version: str = Field(..., description="Scoring model version identifier")
    subject_id: str = Field(..., description="SHA-256 hashed subject identifier")
    metadata: ScoreMetadata


# ---------------------------------------------------------------------------
# Pro endpoint — BRD §9.3.1
# ---------------------------------------------------------------------------


class ScoreProResponse(BaseModel):
    """Response for GET /v1/scores/pro/{nationalId} (BRD §9.3.1)."""

    vyce_score: int = Field(..., ge=300, le=900, description="VyceScore credit score")
    niq_score: int = Field(..., ge=0, le=100, description="Network Interdependence & Quality score")
    risk_drivers: list[RiskDriverResponse] = Field(
        ...,
        min_length=1,
        max_length=3,
        description="Top risk drivers with SHAP explainability",
    )
    score_date: str = Field(..., description="Date the score was computed (ISO 8601)")
    model_version: str = Field(..., description="ML model version used")
    prediction_horizon: str = Field(
        ...,
        description="Prediction time horizon, e.g. '12_months'",
    )
    confidence_interval: ConfidenceInterval
    interpretation: ScoreInterpretation


class ScoreHistoryItem(BaseModel):
    """A single historical score entry."""

    vyce_score: int = Field(..., ge=300, le=900)
    niq_score: int = Field(..., ge=0, le=100)
    score_date: str
    model_version: str


class ScoreProWithHistoryResponse(ScoreProResponse):
    """Pro response extended with score history (BRD §9.3.1 includeHistory)."""

    history: list[ScoreHistoryItem] = Field(
        default_factory=list,
        description="Historical scores over the last 12 months",
    )


# ---------------------------------------------------------------------------
# Batch endpoint
# ---------------------------------------------------------------------------


class ScoreBatchRequest(BaseModel):
    """Batch scoring request body."""

    national_ids: list[str] = Field(..., min_length=1, max_length=100)


class ScoreBatchResponse(BaseModel):
    """Batch scoring response."""

    results: list[ScoreLiteResponse]
    total: int
    failed: int = 0
