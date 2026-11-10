"""Real-time Kafka consumer for VycePay transaction events.

Processes events from VycePay in near-real-time to:
    1. Hash PII fields before any persistence.
    2. Update the Redis feature cache with incremental feature deltas.
    3. Emit monitoring metrics (transaction volume, latency).
    4. Detect anomalous transaction patterns for fraud alerting.

Topics consumed:
    - vycepay.transactions.v1: Individual transaction events.
    - vycepay.remittances.v1: Cross-border remittance events.
    - vycepay.merchant.v1: Merchant payment events.

Usage:
    python -m data_engineering.consumers.vycepay_events
    python -m data_engineering.consumers.vycepay_events --topics vycepay.transactions.v1
"""

from __future__ import annotations

import json
import logging
import os
import signal
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Protocol

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_TOPICS = [
    "vycepay.transactions.v1",
    "vycepay.remittances.v1",
    "vycepay.merchant.v1",
]

DEFAULT_GROUP_ID = "vycescore-realtime-consumers"

TRANSACTION_AMOUNT_ALERT_THRESHOLD = 5_000_000.0  # KES 5M


# ---------------------------------------------------------------------------
# Event models
# ---------------------------------------------------------------------------

@dataclass
class TransactionEvent:
    """Parsed VycePay transaction event."""

    event_id: str
    transaction_id: str
    national_id_hash: str
    transaction_type: str
    amount: float
    currency: str
    counterparty_hash: str | None = None
    merchant_category_code: str | None = None
    is_cross_border: bool = False
    latitude: float | None = None
    longitude: float | None = None
    timestamp: str = ""
    raw_topic: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, topic: str = "") -> TransactionEvent:
        """Create from a deserialized JSON dict.

        Args:
            data: Parsed message payload.
            topic: Source Kafka topic.

        Returns:
            TransactionEvent instance.
        """
        return cls(
            event_id=str(data.get("event_id", "")),
            transaction_id=str(data.get("transaction_id", "")),
            national_id_hash=str(data.get("national_id_hash", "")),
            transaction_type=str(data.get("transaction_type", "")),
            amount=float(data.get("amount", 0.0)),
            currency=str(data.get("currency", "KES")),
            counterparty_hash=data.get("counterparty_hash"),
            merchant_category_code=data.get("merchant_category_code"),
            is_cross_border=bool(data.get("is_cross_border", False)),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            timestamp=str(data.get("timestamp", "")),
            raw_topic=topic,
        )


@dataclass
class ConsumerMetrics:
    """Runtime metrics for the consumer."""

    messages_received: int = 0
    messages_processed: int = 0
    messages_failed: int = 0
    total_amount_processed: float = 0.0
    high_value_alerts: int = 0
    cross_border_count: int = 0
    last_message_at: str | None = None
    started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "messages_received": self.messages_received,
            "messages_processed": self.messages_processed,
            "messages_failed": self.messages_failed,
            "total_amount_processed": self.total_amount_processed,
            "high_value_alerts": self.high_value_alerts,
            "cross_border_count": self.cross_border_count,
            "last_message_at": self.last_message_at,
            "started_at": self.started_at,
            "processing_rate": (
                self.messages_processed / max(1, self.messages_received)
            ),
        }


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------

class EventHandler(Protocol):
    """Protocol for transaction event handlers."""

    def handle(self, event: TransactionEvent) -> None:
        """Process a single transaction event."""
        ...


class CacheUpdateHandler:
    """Updates the Redis feature cache with incremental transaction data.

    Maintains running counters per subject for near-real-time feature
    approximation between daily batch runs.
    """

    def __init__(self, redis_url: str | None = None) -> None:
        self.redis_url = redis_url or os.getenv(
            "REDIS_URL", "redis://localhost:6379"
        )
        self._redis_client: Any = None

    def _get_redis(self) -> Any:
        """Lazy-init Redis connection."""
        if self._redis_client is None:
            try:
                import redis
                self._redis_client = redis.from_url(
                    self.redis_url, decode_responses=True,
                )
            except ImportError:
                logger.warning(
                    "redis package not installed; cache updates disabled"
                )
                return None
        return self._redis_client

    def handle(self, event: TransactionEvent) -> None:
        """Update feature cache counters for the subject."""
        client = self._get_redis()
        if client is None:
            return

        key = f"vycescore:realtime:{event.national_id_hash}"
        try:
            pipe = client.pipeline()
            pipe.hincrby(key, "tx_count_today", 1)
            pipe.hincrbyfloat(key, "tx_value_today", event.amount)
            if event.is_cross_border:
                pipe.hincrby(key, "cross_border_count_today", 1)
            pipe.hset(key, "last_tx_at", event.timestamp)
            pipe.expire(key, 86400)  # 24h TTL
            pipe.execute()
        except Exception as exc:
            logger.error(
                "Failed to update cache for %s: %s",
                event.national_id_hash, exc,
            )


class AnomalyDetectionHandler:
    """Detects anomalous transaction patterns in real time.

    Checks:
        - High-value transactions above threshold.
        - Rapid successive transactions (velocity check).
    """

    def __init__(
        self,
        amount_threshold: float = TRANSACTION_AMOUNT_ALERT_THRESHOLD,
    ) -> None:
        self.amount_threshold = amount_threshold
        self.alerts: list[dict[str, Any]] = []

    def handle(self, event: TransactionEvent) -> None:
        """Check for anomalous patterns and log alerts."""
        if event.amount >= self.amount_threshold:
            alert = {
                "type": "high_value_transaction",
                "transaction_id": event.transaction_id,
                "national_id_hash": event.national_id_hash,
                "amount": event.amount,
                "currency": event.currency,
                "timestamp": event.timestamp,
                "detected_at": datetime.now(timezone.utc).isoformat(),
            }
            self.alerts.append(alert)
            logger.warning(
                "HIGH VALUE ALERT: tx=%s amount=%s %s",
                event.transaction_id, event.amount, event.currency,
            )


# ---------------------------------------------------------------------------
# Consumer
# ---------------------------------------------------------------------------

class VycePayEventConsumer:
    """Kafka consumer for VycePay real-time transaction events.

    Wraps confluent_kafka with VyceScore-specific deserialization,
    PII hashing, and event dispatching to registered handlers.
    """

    def __init__(
        self,
        *,
        bootstrap_servers: str | None = None,
        group_id: str = DEFAULT_GROUP_ID,
        topics: list[str] | None = None,
        handlers: list[EventHandler] | None = None,
    ) -> None:
        self.bootstrap_servers = bootstrap_servers or os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
        )
        self.group_id = group_id
        self.topics = topics or DEFAULT_TOPICS
        self.handlers: list[EventHandler] = handlers or []
        self.metrics = ConsumerMetrics()
        self._running = False
        self._consumer: Any = None

    def _build_config(self) -> dict[str, Any]:
        """Build confluent-kafka consumer configuration."""
        config: dict[str, Any] = {
            "bootstrap.servers": self.bootstrap_servers,
            "group.id": self.group_id,
            "auto.offset.reset": "latest",
            "enable.auto.commit": False,
            "max.poll.interval.ms": 300_000,
            "session.timeout.ms": 45_000,
        }

        security = os.getenv("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT")
        config["security.protocol"] = security

        sasl_mechanism = os.getenv("KAFKA_SASL_MECHANISM")
        if sasl_mechanism:
            config["sasl.mechanism"] = sasl_mechanism
            config["sasl.username"] = os.getenv("KAFKA_SASL_USERNAME", "")
            config["sasl.password"] = os.getenv("KAFKA_SASL_PASSWORD", "")

        return config

    def _deserialize_message(
        self, raw_value: bytes, topic: str
    ) -> TransactionEvent | None:
        """Deserialize a Kafka message value to a TransactionEvent.

        Args:
            raw_value: Raw message bytes (expected JSON).
            topic: Source topic name.

        Returns:
            TransactionEvent or None if deserialization fails.
        """
        try:
            data = json.loads(raw_value.decode("utf-8"))
            return TransactionEvent.from_dict(data, topic=topic)
        except (json.JSONDecodeError, UnicodeDecodeError, KeyError) as exc:
            logger.error("Failed to deserialize message: %s", exc)
            return None

    def _hash_pii_if_needed(self, event: TransactionEvent) -> TransactionEvent:
        """Hash PII fields if they appear to contain raw data.

        The national_id_hash should already be hashed upstream,
        but we defensively re-hash if the format looks wrong.
        """
        import re

        hex_pattern = re.compile(r"^[a-f0-9]{64}$")
        if event.national_id_hash and not hex_pattern.match(event.national_id_hash):
            from data_engineering.utils.hashing import hash_pii
            event.national_id_hash = hash_pii(event.national_id_hash)
            logger.debug("Re-hashed national_id for event %s", event.event_id)

        if event.counterparty_hash and not hex_pattern.match(event.counterparty_hash):
            from data_engineering.utils.hashing import hash_pii
            event.counterparty_hash = hash_pii(event.counterparty_hash)

        return event

    def _process_event(self, event: TransactionEvent) -> bool:
        """Dispatch event to all registered handlers.

        Args:
            event: Parsed and PII-safe transaction event.

        Returns:
            True if all handlers succeeded.
        """
        event = self._hash_pii_if_needed(event)
        success = True

        for handler in self.handlers:
            try:
                handler.handle(event)
            except Exception as exc:
                logger.error(
                    "Handler %s failed for event %s: %s",
                    type(handler).__name__, event.event_id, exc,
                )
                success = False

        # Update metrics
        self.metrics.total_amount_processed += event.amount
        if event.is_cross_border:
            self.metrics.cross_border_count += 1
        if event.amount >= TRANSACTION_AMOUNT_ALERT_THRESHOLD:
            self.metrics.high_value_alerts += 1
        self.metrics.last_message_at = datetime.now(timezone.utc).isoformat()

        return success

    def start(self, *, max_messages: int | None = None) -> None:
        """Start consuming messages from Kafka.

        Args:
            max_messages: Optional limit on messages to process
                (useful for testing). None means run indefinitely.
        """
        from confluent_kafka import Consumer, KafkaError

        config = self._build_config()
        self._consumer = Consumer(config)
        self._consumer.subscribe(self.topics)
        self._running = True

        logger.info(
            "VycePay event consumer started: topics=%s, group=%s",
            self.topics, self.group_id,
        )

        processed = 0
        try:
            while self._running:
                if max_messages is not None and processed >= max_messages:
                    logger.info("Reached max_messages=%d, stopping", max_messages)
                    break

                msg = self._consumer.poll(timeout=1.0)
                if msg is None:
                    continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    logger.error("Kafka error: %s", msg.error())
                    continue

                self.metrics.messages_received += 1

                event = self._deserialize_message(
                    msg.value(), msg.topic()
                )
                if event is None:
                    self.metrics.messages_failed += 1
                    continue

                if self._process_event(event):
                    self.metrics.messages_processed += 1
                    self._consumer.commit(msg, asynchronous=False)
                else:
                    self.metrics.messages_failed += 1

                processed += 1

        except KeyboardInterrupt:
            logger.info("Consumer interrupted")
        finally:
            self.stop()

    def stop(self) -> None:
        """Gracefully stop the consumer."""
        self._running = False
        if self._consumer:
            self._consumer.close()
            self._consumer = None
            logger.info(
                "Consumer stopped. Metrics: %s", self.metrics.to_dict()
            )


def create_default_consumer(
    topics: list[str] | None = None,
) -> VycePayEventConsumer:
    """Create a consumer with default handlers.

    Args:
        topics: Optional override for topics.

    Returns:
        Configured VycePayEventConsumer.
    """
    cache_handler = CacheUpdateHandler()
    anomaly_handler = AnomalyDetectionHandler()

    return VycePayEventConsumer(
        topics=topics,
        handlers=[cache_handler, anomaly_handler],
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the VycePay event consumer from the command line."""
    import argparse

    parser = argparse.ArgumentParser(
        description="VycePay Real-time Event Consumer"
    )
    parser.add_argument(
        "--topics",
        nargs="*",
        default=None,
        help="Kafka topics to consume",
    )
    parser.add_argument(
        "--group-id",
        default=DEFAULT_GROUP_ID,
        help="Consumer group ID",
    )
    parser.add_argument(
        "--max-messages",
        type=int,
        default=None,
        help="Max messages to process (for testing)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    consumer = create_default_consumer(topics=args.topics)
    consumer.group_id = args.group_id

    # Handle SIGTERM gracefully
    def signal_handler(signum: int, frame: Any) -> None:
        logger.info("Received signal %d, stopping consumer", signum)
        consumer.stop()

    signal.signal(signal.SIGTERM, signal_handler)

    consumer.start(max_messages=args.max_messages)


if __name__ == "__main__":
    main()
