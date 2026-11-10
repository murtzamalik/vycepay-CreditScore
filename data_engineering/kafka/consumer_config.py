"""
Kafka consumer configuration for VycePay real-time transaction events.

Consumers process real-time transaction events from VycePay for:
    - Near-real-time feature updates (cache warming)
    - Fraud signal detection
    - Transaction volume monitoring

Consumer group: vycescore-feature-consumers
Topics:
    - vycepay.transactions.v1: Raw transaction events
    - vycepay.remittances.v1: Remittance events
    - vycepay.merchant.v1: Merchant activity events
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from confluent_kafka import Consumer, KafkaError, KafkaException, Message


@dataclass
class VycePayConsumerConfig:
    """Configuration for the VycePay Kafka consumer.

    Attributes:
        bootstrap_servers: Comma-separated list of Kafka broker addresses.
        group_id: Consumer group identifier.
        topics: List of topics to subscribe to.
        auto_offset_reset: Where to start reading when no offset exists.
        enable_auto_commit: Whether to auto-commit offsets.
        max_poll_interval_ms: Maximum interval between poll calls.
        session_timeout_ms: Consumer session timeout.
        security_protocol: Security protocol for broker connection.
        sasl_mechanism: SASL mechanism if using SASL auth.
        sasl_username: SASL username (from env var).
        sasl_password: SASL password (from env var).
    """

    bootstrap_servers: str = field(
        default_factory=lambda: os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    )
    group_id: str = "vycescore-feature-consumers"
    topics: list[str] = field(default_factory=lambda: [
        "vycepay.transactions.v1",
        "vycepay.remittances.v1",
        "vycepay.merchant.v1",
    ])
    auto_offset_reset: str = "latest"
    enable_auto_commit: bool = False  # Manual commit for exactly-once processing
    max_poll_interval_ms: int = 300_000  # 5 minutes
    session_timeout_ms: int = 45_000  # 45 seconds
    security_protocol: str = field(
        default_factory=lambda: os.getenv("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT")
    )
    sasl_mechanism: str | None = field(
        default_factory=lambda: os.getenv("KAFKA_SASL_MECHANISM")
    )
    sasl_username: str | None = field(
        default_factory=lambda: os.getenv("KAFKA_SASL_USERNAME")
    )
    sasl_password: str | None = field(
        default_factory=lambda: os.getenv("KAFKA_SASL_PASSWORD")
    )

    def to_confluent_config(self) -> dict[str, Any]:
        """Convert to confluent-kafka consumer configuration dict.

        Returns:
            Dictionary suitable for passing to confluent_kafka.Consumer().
        """
        config: dict[str, Any] = {
            "bootstrap.servers": self.bootstrap_servers,
            "group.id": self.group_id,
            "auto.offset.reset": self.auto_offset_reset,
            "enable.auto.commit": self.enable_auto_commit,
            "max.poll.interval.ms": self.max_poll_interval_ms,
            "session.timeout.ms": self.session_timeout_ms,
            "security.protocol": self.security_protocol,
        }

        if self.sasl_mechanism:
            config["sasl.mechanism"] = self.sasl_mechanism
        if self.sasl_username:
            config["sasl.username"] = self.sasl_username
        if self.sasl_password:
            config["sasl.password"] = self.sasl_password

        return config


class VycePayConsumer:
    """Kafka consumer for VycePay real-time transaction events.

    Wraps confluent_kafka.Consumer with VyceScore-specific configuration,
    error handling, and message processing logic.

    Usage::

        config = VycePayConsumerConfig()
        consumer = VycePayConsumer(config)
        consumer.start(message_handler=process_transaction)
    """

    def __init__(self, config: VycePayConsumerConfig) -> None:
        self._config = config
        self._consumer: Consumer | None = None
        self._running = False

    def _create_consumer(self) -> Consumer:
        """Create and configure the confluent-kafka Consumer instance."""
        return Consumer(self._config.to_confluent_config())

    def start(
        self,
        message_handler: Callable[[Message], None],
        error_handler: Optional[Callable[[KafkaError], None]] = None,
        poll_timeout: float = 1.0,
    ) -> None:
        """Start consuming messages from the configured topics.

        Args:
            message_handler: Callable invoked for each successfully received message.
            error_handler: Optional callable for handling Kafka errors.
            poll_timeout: Timeout in seconds for each poll call.
        """
        self._consumer = self._create_consumer()
        self._consumer.subscribe(self._config.topics)
        self._running = True

        print(f"VycePay consumer started. Topics: {self._config.topics}")

        try:
            while self._running:
                msg = self._consumer.poll(timeout=poll_timeout)

                if msg is None:
                    continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    if error_handler:
                        error_handler(msg.error())
                    else:
                        print(f"Consumer error: {msg.error()}")
                    continue

                try:
                    message_handler(msg)
                    # Manual commit after successful processing
                    self._consumer.commit(msg, asynchronous=False)
                except Exception as e:
                    print(f"Error processing message: {e}")
                    # Do NOT commit -- message will be redelivered

        except KeyboardInterrupt:
            print("Consumer interrupted by user")
        finally:
            self.stop()

    def stop(self) -> None:
        """Gracefully stop the consumer and close the connection."""
        self._running = False
        if self._consumer:
            self._consumer.close()
            print("VycePay consumer stopped")


def default_message_handler(msg: Message) -> None:
    """Default handler that logs the received message.

    In production, this would:
        1. Deserialize the Avro/JSON message
        2. Hash any PII fields
        3. Update the near-real-time feature cache
        4. Emit monitoring metrics

    Args:
        msg: Kafka message from VycePay topic.
    """
    print(
        f"Received: topic={msg.topic()}, partition={msg.partition()}, "
        f"offset={msg.offset()}, key={msg.key()}, "
        f"value_size={len(msg.value()) if msg.value() else 0} bytes"
    )


if __name__ == "__main__":
    config = VycePayConsumerConfig()
    consumer = VycePayConsumer(config)
    consumer.start(message_handler=default_message_handler)
