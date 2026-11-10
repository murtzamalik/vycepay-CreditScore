"""Retraining triggers for the VyceScore active learning loop.

Defines the conditions under which automated model retraining is triggered:
    1. **Volume trigger**: 1000+ new ground truth labels collected since last
       retraining.
    2. **Performance trigger**: AUC-ROC of the production model drops below 0.72.
    3. **Scheduled trigger**: Monthly retraining (configurable).
    4. **Manual trigger**: Explicit operator or admin request.
    5. **Drift trigger**: Feature distribution drift (PSI) above threshold.

The ``check_all_triggers`` function evaluates all conditions and returns
a list of triggered reasons, suitable for use by an orchestrator (Airflow
DAG, Celery task, or manual invocation).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class TriggerType(str, Enum):
    """Type of retraining trigger."""

    VOLUME = "volume"
    PERFORMANCE = "performance"
    SCHEDULED = "scheduled"
    MANUAL = "manual"
    DRIFT = "drift"


@dataclass(frozen=True)
class TriggerConfig:
    """Configuration for retraining triggers.

    Attributes:
        min_new_labels: Number of new ground truth labels required to
            trigger retraining.
        auc_roc_floor: AUC-ROC threshold below which retraining is triggered.
        schedule_interval_days: Days between scheduled retraining runs.
        drift_psi_threshold: PSI threshold above which drift triggers
            retraining.
        enabled_triggers: Set of trigger types that are active.
    """

    min_new_labels: int = 1000
    auc_roc_floor: float = 0.72
    schedule_interval_days: int = 30
    drift_psi_threshold: float = 0.25
    enabled_triggers: frozenset[TriggerType] = frozenset(TriggerType)


@dataclass(frozen=True)
class TriggerResult:
    """Result of a single trigger check.

    Attributes:
        trigger_type: Type of trigger evaluated.
        triggered: Whether this trigger fired.
        reason: Human-readable reason for the trigger decision.
        details: Additional context for logging/auditing.
    """

    trigger_type: TriggerType
    triggered: bool
    reason: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class TriggerCheckResult:
    """Aggregate result from checking all triggers.

    Attributes:
        should_retrain: True if at least one trigger fired.
        triggered_reasons: List of individual trigger results that fired.
        all_results: All trigger check results.
        checked_at: UTC timestamp of the check.
    """

    should_retrain: bool
    triggered_reasons: list[TriggerResult]
    all_results: list[TriggerResult]
    checked_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


def check_volume_trigger(
    new_labels_count: int,
    config: TriggerConfig | None = None,
) -> TriggerResult:
    """Check if enough new ground truth labels have been collected.

    Args:
        new_labels_count: Number of new ground truth labels since last
            retraining.
        config: Trigger configuration.

    Returns:
        TriggerResult indicating whether the volume threshold is met.
    """
    if config is None:
        config = TriggerConfig()

    triggered = new_labels_count >= config.min_new_labels
    reason = (
        f"Volume trigger: {new_labels_count} new labels collected "
        f"(threshold: {config.min_new_labels})."
    )

    if triggered:
        logger.info("Volume trigger FIRED: %s", reason)
    else:
        logger.debug("Volume trigger not met: %s", reason)

    return TriggerResult(
        trigger_type=TriggerType.VOLUME,
        triggered=triggered,
        reason=reason,
        details={
            "new_labels_count": new_labels_count,
            "threshold": config.min_new_labels,
        },
    )


def check_performance_trigger(
    current_auc_roc: float,
    config: TriggerConfig | None = None,
) -> TriggerResult:
    """Check if production model AUC-ROC has dropped below the floor.

    Args:
        current_auc_roc: Current production model AUC-ROC.
        config: Trigger configuration.

    Returns:
        TriggerResult indicating whether performance degradation is detected.
    """
    if config is None:
        config = TriggerConfig()

    triggered = current_auc_roc < config.auc_roc_floor
    reason = (
        f"Performance trigger: AUC-ROC = {current_auc_roc:.4f} "
        f"(floor: {config.auc_roc_floor})."
    )

    if triggered:
        logger.warning("Performance trigger FIRED: %s", reason)
    else:
        logger.debug("Performance trigger not met: %s", reason)

    return TriggerResult(
        trigger_type=TriggerType.PERFORMANCE,
        triggered=triggered,
        reason=reason,
        details={
            "current_auc_roc": current_auc_roc,
            "floor": config.auc_roc_floor,
        },
    )


def check_scheduled_trigger(
    last_retrain_date: datetime | None,
    config: TriggerConfig | None = None,
) -> TriggerResult:
    """Check if enough time has elapsed since the last retraining.

    Args:
        last_retrain_date: UTC timestamp of the last retraining run.
            If None, trigger fires immediately.
        config: Trigger configuration.

    Returns:
        TriggerResult indicating whether the schedule interval has elapsed.
    """
    if config is None:
        config = TriggerConfig()

    now = datetime.now(timezone.utc)

    if last_retrain_date is None:
        return TriggerResult(
            trigger_type=TriggerType.SCHEDULED,
            triggered=True,
            reason="Scheduled trigger: no previous retraining recorded.",
            details={"last_retrain_date": None, "interval_days": config.schedule_interval_days},
        )

    elapsed = now - last_retrain_date
    triggered = elapsed >= timedelta(days=config.schedule_interval_days)
    reason = (
        f"Scheduled trigger: {elapsed.days} days since last retrain "
        f"(interval: {config.schedule_interval_days} days)."
    )

    if triggered:
        logger.info("Scheduled trigger FIRED: %s", reason)
    else:
        logger.debug("Scheduled trigger not met: %s", reason)

    return TriggerResult(
        trigger_type=TriggerType.SCHEDULED,
        triggered=triggered,
        reason=reason,
        details={
            "last_retrain_date": last_retrain_date.isoformat(),
            "elapsed_days": elapsed.days,
            "interval_days": config.schedule_interval_days,
        },
    )


def check_manual_trigger(
    manual_requested: bool = False,
    requested_by: str | None = None,
) -> TriggerResult:
    """Check if a manual retraining has been requested.

    Args:
        manual_requested: Whether an operator has requested retraining.
        requested_by: Identifier of the user who requested retraining.

    Returns:
        TriggerResult indicating whether a manual trigger was issued.
    """
    reason = (
        f"Manual trigger: requested by {requested_by or 'unknown'}."
        if manual_requested
        else "Manual trigger: not requested."
    )

    if manual_requested:
        logger.info("Manual trigger FIRED: %s", reason)

    return TriggerResult(
        trigger_type=TriggerType.MANUAL,
        triggered=manual_requested,
        reason=reason,
        details={"requested_by": requested_by},
    )


def check_drift_trigger(
    max_feature_psi: float,
    config: TriggerConfig | None = None,
) -> TriggerResult:
    """Check if feature drift exceeds the PSI threshold.

    Args:
        max_feature_psi: Maximum PSI value across all features.
        config: Trigger configuration.

    Returns:
        TriggerResult indicating whether drift triggers retraining.
    """
    if config is None:
        config = TriggerConfig()

    triggered = max_feature_psi > config.drift_psi_threshold
    reason = (
        f"Drift trigger: max PSI = {max_feature_psi:.4f} "
        f"(threshold: {config.drift_psi_threshold})."
    )

    if triggered:
        logger.warning("Drift trigger FIRED: %s", reason)
    else:
        logger.debug("Drift trigger not met: %s", reason)

    return TriggerResult(
        trigger_type=TriggerType.DRIFT,
        triggered=triggered,
        reason=reason,
        details={
            "max_feature_psi": max_feature_psi,
            "threshold": config.drift_psi_threshold,
        },
    )


def check_all_triggers(
    new_labels_count: int = 0,
    current_auc_roc: float = 1.0,
    last_retrain_date: datetime | None = None,
    manual_requested: bool = False,
    requested_by: str | None = None,
    max_feature_psi: float = 0.0,
    config: TriggerConfig | None = None,
) -> TriggerCheckResult:
    """Evaluate all retraining triggers and return aggregate result.

    Args:
        new_labels_count: New ground truth labels since last retrain.
        current_auc_roc: Current production model AUC-ROC.
        last_retrain_date: UTC timestamp of last retraining.
        manual_requested: Whether manual retraining was requested.
        requested_by: Who requested manual retraining.
        max_feature_psi: Maximum feature PSI value.
        config: Trigger configuration.

    Returns:
        TriggerCheckResult with aggregated results.
    """
    if config is None:
        config = TriggerConfig()

    all_results: list[TriggerResult] = []

    if TriggerType.VOLUME in config.enabled_triggers:
        all_results.append(check_volume_trigger(new_labels_count, config))

    if TriggerType.PERFORMANCE in config.enabled_triggers:
        all_results.append(check_performance_trigger(current_auc_roc, config))

    if TriggerType.SCHEDULED in config.enabled_triggers:
        all_results.append(check_scheduled_trigger(last_retrain_date, config))

    if TriggerType.MANUAL in config.enabled_triggers:
        all_results.append(
            check_manual_trigger(manual_requested, requested_by)
        )

    if TriggerType.DRIFT in config.enabled_triggers:
        all_results.append(check_drift_trigger(max_feature_psi, config))

    triggered = [r for r in all_results if r.triggered]
    should_retrain = len(triggered) > 0

    if should_retrain:
        reasons_str = "; ".join(r.reason for r in triggered)
        logger.info(
            "Retraining TRIGGERED by %d condition(s): %s",
            len(triggered),
            reasons_str,
        )
    else:
        logger.info("No retraining triggers fired.")

    return TriggerCheckResult(
        should_retrain=should_retrain,
        triggered_reasons=triggered,
        all_results=all_results,
    )
