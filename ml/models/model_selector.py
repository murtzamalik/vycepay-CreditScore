"""Dynamic model selection for VyceScore inference.

Selects the best model for a given prediction request based on:
    - Available data quality and quantity for the subject
    - Subject's business category / industry vertical
    - Prediction horizon
    - Whether an industry-specific model has sufficient training data

Falls back to the general model when an industry-specific model does not
have enough training data or is not yet deployed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
import xgboost as xgb

from ml.models.industry_variants import (
    IndustryVertical,
    get_industry_profile,
    get_prediction_horizon_config,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelInfo:
    """Information about a registered model variant.

    Attributes:
        model_id: Unique model identifier.
        vertical: Industry vertical this model is trained for.
        horizon_days: Prediction horizon in days.
        auc_roc: Model AUC-ROC on test set.
        training_samples: Number of training samples used.
        model: The XGBoost model (None if not loaded).
        is_production: Whether this model is in production.
    """

    model_id: str
    vertical: IndustryVertical
    horizon_days: int
    auc_roc: float
    training_samples: int
    model: xgb.XGBClassifier | None = None
    is_production: bool = False


@dataclass
class SelectionResult:
    """Result of dynamic model selection.

    Attributes:
        selected_model: The ModelInfo that was selected.
        reason: Explanation for the selection.
        fallback_used: Whether a fallback model was used.
        data_quality: Assessed data quality (high/medium/low).
    """

    selected_model: ModelInfo
    reason: str
    fallback_used: bool = False
    data_quality: str = "high"


class ModelSelector:
    """Select the best model based on context.

    Maintains a registry of model variants and selects the most
    appropriate one for each prediction request.

    Args:
        general_model: The fallback general model (always available).
        general_model_info: ModelInfo for the general model.
    """

    def __init__(
        self,
        general_model: xgb.XGBClassifier,
        general_model_info: ModelInfo | None = None,
    ) -> None:
        self._general_model = general_model
        self._general_info = general_model_info or ModelInfo(
            model_id="general-default",
            vertical=IndustryVertical.GENERAL,
            horizon_days=365,
            auc_roc=0.0,
            training_samples=0,
            model=general_model,
            is_production=True,
        )
        self._registry: dict[str, ModelInfo] = {
            self._general_info.model_id: self._general_info
        }

    def register_model(self, model_info: ModelInfo) -> None:
        """Register a model variant in the selector.

        Args:
            model_info: ModelInfo describing the variant.
        """
        self._registry[model_info.model_id] = model_info
        logger.info(
            "Registered model '%s' (vertical=%s, horizon=%dd, AUC=%.4f).",
            model_info.model_id,
            model_info.vertical.value,
            model_info.horizon_days,
            model_info.auc_roc,
        )

    def unregister_model(self, model_id: str) -> None:
        """Remove a model from the registry.

        Args:
            model_id: Model identifier to remove.
        """
        if model_id == self._general_info.model_id:
            raise ValueError("Cannot unregister the general (fallback) model.")
        self._registry.pop(model_id, None)

    def select(
        self,
        vertical: IndustryVertical | str | None = None,
        horizon_days: int = 365,
        available_features: list[str] | None = None,
        data_completeness: float = 1.0,
    ) -> SelectionResult:
        """Select the best model for a given context.

        Selection logic:
            1. Look for an industry-specific model matching the vertical
               and horizon.
            2. If found and has sufficient training data, use it.
            3. Otherwise, fall back to the general model.
            4. If data quality is low, prefer the general model (more robust).

        Args:
            vertical: Requested industry vertical.
            horizon_days: Prediction horizon in days.
            available_features: Features available for the subject.
            data_completeness: Fraction of required data available (0-1).

        Returns:
            SelectionResult with the chosen model and explanation.
        """
        # Resolve vertical
        if vertical is None:
            vertical_enum = IndustryVertical.GENERAL
        elif isinstance(vertical, str):
            try:
                vertical_enum = IndustryVertical(vertical.lower())
            except ValueError:
                logger.warning(
                    "Unknown vertical '%s'; falling back to general.", vertical
                )
                vertical_enum = IndustryVertical.GENERAL
        else:
            vertical_enum = vertical

        # Assess data quality
        data_quality = _assess_data_quality(data_completeness, available_features)

        # Low data quality -> always use general model (most robust)
        if data_quality == "low":
            return SelectionResult(
                selected_model=self._general_info,
                reason="Data quality is low; using general model for robustness.",
                fallback_used=True,
                data_quality=data_quality,
            )

        # Look for a matching industry-specific model
        if vertical_enum != IndustryVertical.GENERAL:
            candidates = [
                info
                for info in self._registry.values()
                if info.vertical == vertical_enum
                and info.horizon_days == horizon_days
                and info.model is not None
            ]

            if candidates:
                # Pick the one with highest AUC-ROC
                best = max(candidates, key=lambda m: m.auc_roc)
                profile = get_industry_profile(vertical_enum)

                if best.training_samples >= profile.min_training_samples:
                    return SelectionResult(
                        selected_model=best,
                        reason=(
                            f"Industry-specific model for {vertical_enum.value} "
                            f"({best.training_samples} training samples, "
                            f"AUC={best.auc_roc:.4f})."
                        ),
                        fallback_used=False,
                        data_quality=data_quality,
                    )
                else:
                    logger.info(
                        "Industry model for %s has insufficient training data "
                        "(%d < %d); falling back to general.",
                        vertical_enum.value,
                        best.training_samples,
                        profile.min_training_samples,
                    )

        # Fallback to general model
        return SelectionResult(
            selected_model=self._general_info,
            reason=(
                f"Using general model (no qualified {vertical_enum.value} "
                f"model available for horizon={horizon_days}d)."
            ),
            fallback_used=vertical_enum != IndustryVertical.GENERAL,
            data_quality=data_quality,
        )

    def list_models(self) -> list[dict[str, Any]]:
        """List all registered model variants.

        Returns:
            List of dicts describing each registered model.
        """
        return [
            {
                "model_id": info.model_id,
                "vertical": info.vertical.value,
                "horizon_days": info.horizon_days,
                "auc_roc": info.auc_roc,
                "training_samples": info.training_samples,
                "is_production": info.is_production,
                "loaded": info.model is not None,
            }
            for info in self._registry.values()
        ]


def _assess_data_quality(
    completeness: float,
    available_features: list[str] | None = None,
) -> str:
    """Assess data quality based on completeness and feature availability.

    Returns:
        "high", "medium", or "low".
    """
    from ml.training.pipeline import CORE_FEATURES

    if available_features is not None:
        core_present = sum(
            1 for f in CORE_FEATURES if f in available_features
        )
        feature_ratio = core_present / len(CORE_FEATURES)
    else:
        feature_ratio = 1.0

    combined = (completeness + feature_ratio) / 2.0

    if combined >= 0.8:
        return "high"
    elif combined >= 0.5:
        return "medium"
    else:
        return "low"
