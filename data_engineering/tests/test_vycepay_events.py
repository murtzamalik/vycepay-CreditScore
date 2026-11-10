"""Tests for VycePay real-time event consumer (Task 5.10)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from data_engineering.consumers.vycepay_events import (
    AnomalyDetectionHandler,
    CacheUpdateHandler,
    ConsumerMetrics,
    TransactionEvent,
    VycePayEventConsumer,
    create_default_consumer,
)


class TestTransactionEvent:
    """Tests for TransactionEvent model."""

    def test_from_dict(self) -> None:
        data = {
            "event_id": "evt_001",
            "transaction_id": "tx_001",
            "national_id_hash": "a" * 64,
            "transaction_type": "FT",
            "amount": 5000.0,
            "currency": "KES",
            "is_cross_border": False,
        }
        event = TransactionEvent.from_dict(data, topic="vycepay.transactions.v1")
        assert event.event_id == "evt_001"
        assert event.amount == 5000.0
        assert event.raw_topic == "vycepay.transactions.v1"
        assert event.is_cross_border is False

    def test_from_dict_with_defaults(self) -> None:
        event = TransactionEvent.from_dict({})
        assert event.amount == 0.0
        assert event.currency == "KES"
        assert event.counterparty_hash is None

    def test_from_dict_cross_border(self) -> None:
        data = {
            "event_id": "evt_002",
            "transaction_id": "tx_002",
            "national_id_hash": "b" * 64,
            "transaction_type": "REMIT",
            "amount": 100_000.0,
            "currency": "USD",
            "is_cross_border": True,
        }
        event = TransactionEvent.from_dict(data)
        assert event.is_cross_border is True
        assert event.currency == "USD"


class TestConsumerMetrics:
    """Tests for ConsumerMetrics."""

    def test_default_metrics(self) -> None:
        metrics = ConsumerMetrics()
        assert metrics.messages_received == 0
        assert metrics.messages_processed == 0
        assert metrics.messages_failed == 0

    def test_to_dict(self) -> None:
        metrics = ConsumerMetrics(
            messages_received=100,
            messages_processed=95,
            messages_failed=5,
        )
        d = metrics.to_dict()
        assert d["messages_received"] == 100
        assert d["processing_rate"] == 0.95


class TestAnomalyDetectionHandler:
    """Tests for AnomalyDetectionHandler."""

    def test_detects_high_value_transaction(self) -> None:
        handler = AnomalyDetectionHandler(amount_threshold=1_000_000)
        event = TransactionEvent(
            event_id="evt_1",
            transaction_id="tx_1",
            national_id_hash="a" * 64,
            transaction_type="FT",
            amount=5_000_000.0,
            currency="KES",
        )
        handler.handle(event)
        assert len(handler.alerts) == 1
        assert handler.alerts[0]["type"] == "high_value_transaction"

    def test_no_alert_for_normal_transaction(self) -> None:
        handler = AnomalyDetectionHandler(amount_threshold=1_000_000)
        event = TransactionEvent(
            event_id="evt_1",
            transaction_id="tx_1",
            national_id_hash="a" * 64,
            transaction_type="FT",
            amount=5_000.0,
            currency="KES",
        )
        handler.handle(event)
        assert len(handler.alerts) == 0

    def test_multiple_alerts_accumulate(self) -> None:
        handler = AnomalyDetectionHandler(amount_threshold=100)
        for i in range(3):
            event = TransactionEvent(
                event_id=f"evt_{i}",
                transaction_id=f"tx_{i}",
                national_id_hash="a" * 64,
                transaction_type="FT",
                amount=500.0,
                currency="KES",
            )
            handler.handle(event)
        assert len(handler.alerts) == 3


class TestVycePayEventConsumer:
    """Tests for VycePayEventConsumer."""

    def test_consumer_initialization(self) -> None:
        consumer = VycePayEventConsumer(
            bootstrap_servers="localhost:9092",
            topics=["test.topic"],
        )
        assert consumer.bootstrap_servers == "localhost:9092"
        assert consumer.topics == ["test.topic"]
        assert len(consumer.handlers) == 0

    def test_build_config(self) -> None:
        consumer = VycePayEventConsumer(
            bootstrap_servers="broker:9092",
            group_id="test-group",
        )
        config = consumer._build_config()
        assert config["bootstrap.servers"] == "broker:9092"
        assert config["group.id"] == "test-group"
        assert config["enable.auto.commit"] is False

    def test_deserialize_valid_json(self) -> None:
        consumer = VycePayEventConsumer()
        raw = b'{"event_id": "e1", "transaction_id": "t1", "amount": 100}'
        event = consumer._deserialize_message(raw, "test.topic")
        assert event is not None
        assert event.event_id == "e1"
        assert event.amount == 100.0

    def test_deserialize_invalid_json(self) -> None:
        consumer = VycePayEventConsumer()
        raw = b"not valid json"
        event = consumer._deserialize_message(raw, "test.topic")
        assert event is None

    def test_process_event_updates_metrics(self) -> None:
        handler = AnomalyDetectionHandler(amount_threshold=1_000_000)
        consumer = VycePayEventConsumer(handlers=[handler])
        event = TransactionEvent(
            event_id="e1",
            transaction_id="t1",
            national_id_hash="a" * 64,
            transaction_type="FT",
            amount=5000.0,
            currency="KES",
        )
        consumer._process_event(event)
        assert consumer.metrics.total_amount_processed == 5000.0

    def test_process_cross_border_event(self) -> None:
        consumer = VycePayEventConsumer()
        event = TransactionEvent(
            event_id="e1",
            transaction_id="t1",
            national_id_hash="a" * 64,
            transaction_type="REMIT",
            amount=10_000.0,
            currency="USD",
            is_cross_border=True,
        )
        consumer._process_event(event)
        assert consumer.metrics.cross_border_count == 1


class TestCreateDefaultConsumer:
    """Tests for create_default_consumer factory."""

    def test_creates_consumer_with_handlers(self) -> None:
        consumer = create_default_consumer()
        assert len(consumer.handlers) == 2

    def test_custom_topics(self) -> None:
        consumer = create_default_consumer(
            topics=["custom.topic.v1"],
        )
        assert consumer.topics == ["custom.topic.v1"]
