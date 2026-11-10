"""SHAP-based explainability for VyceScore credit scoring.

Uses SHAP TreeExplainer for XGBoost models to generate human-readable
risk driver explanations.  This satisfies Kenya's Data Protection Act
(DPA 2019) requirement for "meaningful information about the logic
involved" in automated credit decisions.

Each prediction is accompanied by the top 3 risk drivers, including:
    - A human-readable factor name
    - Impact direction (positive = increases risk, negative = decreases risk)
    - A generated explanation description
    - Contribution percentage of total absolute SHAP
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
import shap
import xgboost as xgb

logger = logging.getLogger(__name__)


# Feature name to human-readable name mapping.
FEATURE_DISPLAY_NAMES: dict[str, str] = {
    "cblri": "Cross-Border Liquidity Resilience",
    "utdi": "Transaction Diversity",
    "scfv": "Supply Chain Formalization",
    "ddc_ratio": "Digital Documentation Compliance",
    "niq_score": "Network Quality Score",
    "gos_index": "Geographic Operational Stability",
    # Extended features
    "avg_daily_balance_30d": "Average Daily Balance (30d)",
    "avg_daily_balance_90d": "Average Daily Balance (90d)",
    "incoming_tx_value_30d": "Incoming Transaction Value (30d)",
    "outgoing_tx_value_30d": "Outgoing Transaction Value (30d)",
    "tx_count_current": "Current Transaction Count",
    "tx_count_mean": "Historical Avg Transaction Count",
    "tx_frequency_30d": "Transaction Frequency (30d)",
    "avg_tx_amount_30d": "Average Transaction Amount (30d)",
    "tx_volume_trend": "Transaction Volume Trend",
    "merchant_category_diversity": "Merchant Category Diversity",
    "supplier_link_count": "Active Supplier Links",
    "invoice_completion_rate": "Invoice Completion Rate",
    "kyc_verification_score": "KYC Verification Score",
    "aml_risk_score": "AML Risk Assessment",
    "task_completion_rate": "Task Completion Rate",
}

# Description templates for risk driver explanations.
_IMPACT_DESCRIPTIONS: dict[str, dict[str, str]] = {
    "cblri": {
        "positive": "Low cross-border liquidity resilience increases default risk",
        "negative": "Strong cross-border liquidity resilience reduces default risk",
    },
    "utdi": {
        "positive": "Limited transaction diversity across merchant categories increases risk",
        "negative": "High transaction diversity across merchant categories reduces risk",
    },
    "scfv": {
        "positive": "Slow supply chain formalization velocity increases risk",
        "negative": "Strong supply chain digitization progress reduces risk",
    },
    "ddc_ratio": {
        "positive": "Low digital documentation compliance increases risk",
        "negative": "High digital documentation compliance reduces risk",
    },
    "niq_score": {
        "positive": "Weak trading partner network quality increases risk",
        "negative": "Strong trading partner network quality reduces risk",
    },
    "gos_index": {
        "positive": "High geographic operational instability increases risk",
        "negative": "Stable geographic operational pattern reduces risk",
    },
}

_DEFAULT_DESCRIPTIONS: dict[str, str] = {
    "positive": "This factor contributes to higher predicted default risk",
    "negative": "This factor contributes to lower predicted default risk",
}


@dataclass(frozen=True)
class RiskDriver:
    """A single risk driver for a credit score prediction.

    Attributes:
        factor: Human-readable feature name.
        impact: Direction of impact — "positive" (increases risk) or
            "negative" (decreases risk).
        description: Human-readable explanation of the impact.
        contribution: Percentage contribution to total absolute SHAP.
        feature_name: Raw feature column name.
        shap_value: Raw SHAP value.
        feature_value: The actual feature value for this prediction.
    """

    factor: str
    impact: str
    description: str
    contribution: float
    feature_name: str
    shap_value: float
    feature_value: float


@dataclass
class ExplanationResult:
    """Complete SHAP explanation for a single prediction.

    Attributes:
        risk_drivers: Top N risk drivers sorted by contribution.
        shap_values: All SHAP values keyed by feature name.
        base_value: SHAP base value (expected model output).
        prediction_probability: Model output probability.
    """

    risk_drivers: list[RiskDriver]
    shap_values: dict[str, float]
    base_value: float
    prediction_probability: float


class VyceScoreExplainer:
    """SHAP TreeExplainer wrapper for VyceScore models.

    Initializes a SHAP TreeExplainer for the given XGBoost model and
    provides methods to explain individual predictions.

    Usage:
        explainer = VyceScoreExplainer(model)
        result = explainer.explain(features_df)
        top_3 = result.risk_drivers  # Already sorted by contribution
    """

    def __init__(
        self,
        model: xgb.XGBClassifier,
        *,
        feature_names: dict[str, str] | None = None,
    ) -> None:
        """Initialize the explainer.

        Args:
            model: Trained XGBoost classifier.
            feature_names: Optional override for feature display name mapping.
                Merged with FEATURE_DISPLAY_NAMES (overrides take priority).
        """
        self._model = model
        self._explainer = shap.TreeExplainer(model)
        self._feature_names: dict[str, str] = {**FEATURE_DISPLAY_NAMES}
        if feature_names:
            self._feature_names.update(feature_names)

    @property
    def explainer(self) -> shap.TreeExplainer:
        """The underlying SHAP TreeExplainer."""
        return self._explainer

    def explain(
        self,
        features: pd.DataFrame,
        *,
        top_n: int = 3,
    ) -> ExplanationResult:
        """Generate a SHAP explanation for a single prediction.

        Args:
            features: Single-row DataFrame with feature values.
            top_n: Number of top risk drivers to return.

        Returns:
            ExplanationResult with risk drivers and full SHAP values.

        Raises:
            ValueError: If features has more than one row.
        """
        if len(features) != 1:
            raise ValueError(
                f"Expected single-row DataFrame, got {len(features)} rows. "
                f"Use explain_batch for multiple predictions."
            )

        shap_values = self._explainer.shap_values(features)

        # Handle both array formats from SHAP
        if isinstance(shap_values, list):
            # Binary classification: shap_values[1] is for the positive class
            shap_row = np.asarray(shap_values[1][0]) if len(shap_values) == 2 else np.asarray(shap_values[0])
        else:
            shap_row = np.asarray(shap_values[0])

        feature_values = features.iloc[0]
        feature_cols = list(features.columns)

        # Get base value
        base_value = self._explainer.expected_value
        if isinstance(base_value, (list, np.ndarray)):
            base_value = float(base_value[1]) if len(base_value) == 2 else float(base_value[0])
        else:
            base_value = float(base_value)

        # Build SHAP values dict
        all_shap: dict[str, float] = {}
        for i, col in enumerate(feature_cols):
            all_shap[col] = float(shap_row[i])

        # Get prediction probability
        prob = float(self._model.predict_proba(features)[:, 1][0])

        # Build risk drivers
        risk_drivers = self._build_risk_drivers(
            shap_row, feature_cols, feature_values, top_n=top_n
        )

        return ExplanationResult(
            risk_drivers=risk_drivers,
            shap_values=all_shap,
            base_value=base_value,
            prediction_probability=prob,
        )

    def explain_batch(
        self,
        features: pd.DataFrame,
        *,
        top_n: int = 3,
    ) -> list[ExplanationResult]:
        """Generate SHAP explanations for multiple predictions.

        Args:
            features: Multi-row DataFrame with feature values.
            top_n: Number of top risk drivers per prediction.

        Returns:
            List of ExplanationResult, one per row.
        """
        results: list[ExplanationResult] = []
        for i in range(len(features)):
            row = features.iloc[[i]]
            results.append(self.explain(row, top_n=top_n))
        return results

    def _build_risk_drivers(
        self,
        shap_row: np.ndarray,
        feature_cols: list[str],
        feature_values: pd.Series,
        *,
        top_n: int = 3,
    ) -> list[RiskDriver]:
        """Build sorted risk drivers from SHAP values.

        Args:
            shap_row: SHAP values for a single prediction.
            feature_cols: Feature column names.
            feature_values: Actual feature values.
            top_n: Number of top drivers to return.

        Returns:
            List of RiskDriver sorted by absolute contribution.
        """
        abs_shap = np.abs(shap_row)
        total_abs_shap = float(np.sum(abs_shap))

        # Sort by absolute SHAP value descending
        top_indices = np.argsort(abs_shap)[::-1][:top_n]

        drivers: list[RiskDriver] = []
        for idx in top_indices:
            col = feature_cols[idx]
            sv = float(shap_row[idx])
            impact = "positive" if sv > 0 else "negative"

            # Human-readable name
            factor = self._feature_names.get(col, col.replace("_", " ").title())

            # Description
            description = self._get_description(col, impact)

            # Contribution percentage
            contribution = (
                abs_shap[idx] / total_abs_shap * 100
                if total_abs_shap > 0
                else 0.0
            )

            drivers.append(RiskDriver(
                factor=factor,
                impact=impact,
                description=description,
                contribution=round(float(contribution), 1),
                feature_name=col,
                shap_value=round(sv, 6),
                feature_value=round(float(feature_values.iloc[idx]), 4),
            ))

        return drivers

    def _get_description(self, feature_name: str, impact: str) -> str:
        """Get a human-readable description for a risk driver.

        Args:
            feature_name: Raw feature column name.
            impact: "positive" or "negative".

        Returns:
            Human-readable description string.
        """
        feature_descs = _IMPACT_DESCRIPTIONS.get(feature_name)
        if feature_descs:
            return feature_descs.get(impact, _DEFAULT_DESCRIPTIONS[impact])
        return _DEFAULT_DESCRIPTIONS[impact]

    def to_api_format(
        self,
        explanation: ExplanationResult,
    ) -> list[dict[str, Any]]:
        """Format risk drivers for API response.

        Produces the format expected by the VyceScore Pro API endpoint.

        Args:
            explanation: ExplanationResult from explain().

        Returns:
            List of dicts suitable for JSON serialization.
        """
        return [
            {
                "factor": d.factor,
                "impact": d.impact,
                "description": d.description,
                "contribution": d.contribution,
            }
            for d in explanation.risk_drivers
        ]
