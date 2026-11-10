"""Tests for ml.active_learning.triggers module."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from ml.active_learning.triggers import (
    TriggerCheckResult,
    TriggerConfig,
    TriggerResult,
    TriggerType,
    check_all_triggers,
    check_drift_trigger,
    check_manual_trigger,
    check_performance_trigger,
    check_scheduled_trigger,
    check_volume_trigger,
)


class TestVolumeTrigger:
    """Tests for check_volume_trigger."""

    def test_fires_at_threshold(self) -> None:
        result = check_volume_trigger(1000)
        assert result.triggered is True
        assert result.trigger_type == TriggerType.VOLUME

    def test_fires_above_threshold(self) -> None:
        result = check_volume_trigger(5000)
        assert result.triggered is True

    def test_does_not_fire_below_threshold(self) -> None:
        result = check_volume_trigger(999)
        assert result.triggered is False

    def test_custom_threshold(self) -> None:
        config = TriggerConfig(min_new_labels=500)
        result = check_volume_trigger(500, config)
        assert result.triggered is True

    def test_zero_labels(self) -> None:
        result = check_volume_trigger(0)
        assert result.triggered is False


class TestPerformanceTrigger:
    """Tests for check_performance_trigger."""

    def test_fires_below_floor(self) -> None:
        result = check_performance_trigger(0.70)
        assert result.triggered is True
        assert result.trigger_type == TriggerType.PERFORMANCE

    def test_does_not_fire_above_floor(self) -> None:
        result = check_performance_trigger(0.80)
        assert result.triggered is False

    def test_fires_at_exactly_floor(self) -> None:
        # 0.72 is not < 0.72
        result = check_performance_trigger(0.72)
        assert result.triggered is False

    def test_custom_floor(self) -> None:
        config = TriggerConfig(auc_roc_floor=0.80)
        result = check_performance_trigger(0.75, config)
        assert result.triggered is True


class TestScheduledTrigger:
    """Tests for check_scheduled_trigger."""

    def test_fires_when_no_previous_retrain(self) -> None:
        result = check_scheduled_trigger(None)
        assert result.triggered is True
        assert result.trigger_type == TriggerType.SCHEDULED

    def test_fires_after_interval(self) -> None:
        old = datetime.now(timezone.utc) - timedelta(days=31)
        result = check_scheduled_trigger(old)
        assert result.triggered is True

    def test_does_not_fire_within_interval(self) -> None:
        recent = datetime.now(timezone.utc) - timedelta(days=15)
        result = check_scheduled_trigger(recent)
        assert result.triggered is False

    def test_custom_interval(self) -> None:
        config = TriggerConfig(schedule_interval_days=7)
        old = datetime.now(timezone.utc) - timedelta(days=8)
        result = check_scheduled_trigger(old, config)
        assert result.triggered is True


class TestManualTrigger:
    """Tests for check_manual_trigger."""

    def test_fires_when_requested(self) -> None:
        result = check_manual_trigger(True, "admin_user")
        assert result.triggered is True
        assert result.trigger_type == TriggerType.MANUAL

    def test_does_not_fire_when_not_requested(self) -> None:
        result = check_manual_trigger(False)
        assert result.triggered is False


class TestDriftTrigger:
    """Tests for check_drift_trigger."""

    def test_fires_above_threshold(self) -> None:
        result = check_drift_trigger(0.30)
        assert result.triggered is True
        assert result.trigger_type == TriggerType.DRIFT

    def test_does_not_fire_below_threshold(self) -> None:
        result = check_drift_trigger(0.10)
        assert result.triggered is False


class TestCheckAllTriggers:
    """Tests for check_all_triggers."""

    def test_returns_aggregated_result(self) -> None:
        result = check_all_triggers(
            new_labels_count=2000,
            current_auc_roc=0.80,
        )
        assert isinstance(result, TriggerCheckResult)
        assert result.should_retrain is True
        assert len(result.triggered_reasons) >= 1

    def test_no_triggers_fired(self) -> None:
        recent = datetime.now(timezone.utc) - timedelta(days=1)
        result = check_all_triggers(
            new_labels_count=0,
            current_auc_roc=0.85,
            last_retrain_date=recent,
            manual_requested=False,
            max_feature_psi=0.01,
        )
        assert result.should_retrain is False
        assert len(result.triggered_reasons) == 0

    def test_multiple_triggers_can_fire(self) -> None:
        result = check_all_triggers(
            new_labels_count=2000,
            current_auc_roc=0.65,
            last_retrain_date=None,
            manual_requested=True,
            requested_by="admin",
            max_feature_psi=0.50,
        )
        assert result.should_retrain is True
        assert len(result.triggered_reasons) >= 4

    def test_disabled_triggers_are_skipped(self) -> None:
        config = TriggerConfig(
            enabled_triggers=frozenset({TriggerType.VOLUME})
        )
        result = check_all_triggers(
            new_labels_count=0,
            current_auc_roc=0.50,  # Would fire performance trigger
            config=config,
        )
        # Only volume checked, and it's 0, so nothing fires
        assert result.should_retrain is False
        assert len(result.all_results) == 1

    def test_checked_at_is_set(self) -> None:
        result = check_all_triggers()
        assert result.checked_at is not None
