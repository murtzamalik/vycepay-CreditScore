"""
Kafka producer configuration for VyceScore event publishing.

Producers publish events for:
    - Score computation completed (consumed by cache refresh, notifications)
    - Feature computation completed (consumed by model inference pipeline)
    - Data quality alerts (consumed by monitoring/alerting)

Topics:
    - vycescore.scores.v1: Newly computed scores
    - vycescore.features.v1: Computed feature vectors
    - vycescore.alerts.v1: Data quality and pipeline alerts
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from confluent_kafka import Producer


@dataclass
class VyceScoreProducerConfig:
    """Configuration for the VyceScore Kafka producer.

    Attributes:
        bootstrap_servers: Comma-separated list of Kafka broker addresses.
        client_id: Producer client identifier.
        acks: Number of acknowledgments required (all for durability).
        retries: Number of retries on transient failures.
        retry_backoff_ms: Backoff between retries.
        linger_ms: Batching linger time for throughput optimization.
        compression_type: Message compression algorithm.
        security_protocol: Security protocol for broker connection.
    """

    bootstrap_servers: str = field(
        default_factory=lambda: os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    )
    client_id: str = "vycescore-producer"
    acks: str = "all"  # Maximum durability
    retries: int = 5
    retry_backoff_ms: int = 500
    linger_ms: int = 50  # Batch messages for 50ms for better throughput
    compression_type: str = "snappy"
    security_protocol: str = field(
        default_factory=lambda: os.getenv("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT")
    )

    def to_confluent_config(self) -> dict[str, Any]:
        """Convert to confluent-kafka producer configuration dict.

        Returns:
            Dictionary suitable for passing to confluent_kafka.Producer().
        """
        return {
            "bootstrap.servers": self.bootstrap_servers,
            "client.id": self.client_id,
            "acks": self.acks,
            "retries": self.retries,
            "retry.backoff.ms": self.retry_backoff_ms,
            "linger.ms": self.linger_ms,
            "compression.type": self.compression_type,
            "security.protocol": self.security_protocol,
        }


class VyceScoreProducer:
    """Kafka producer for VyceScore pipeline events.

    Publishes score completions, feature updates, and alerts to
    downstream consumers.

    Usage::

        config = VyceScoreProducerConfig()
        producer = VyceScoreProducer(config)
        producer.publish_score_event(national_id_hash="abc123...", score=750)
        producer.flush()
    """

    # Topic constants
    TOPIC_SCORES = "vycescore.scores.v1"
    TOPIC_FEATURES = "vycescore.features.v1"
    TOPIC_ALERTS = "vycescore.alerts.v1"

    def __init__(self, config: VyceScoreProducerConfig) -> None:
        self._config = config
        self._producer = Producer(config.to_confluent_config())

    @staticmethod
    def _delivery_callback(err: Any, msg: Any) -> None:
        """Callback invoked on message delivery or failure."""
        if err is not None:
            print(f"Message delivery failed: {err}")
        else:
            print(f"Delivered to {msg.topic()} [{msg.partition()}] @ {msg.offset()}")

    def _publish(
        self,
        topic: str,
        key: str,
        value: dict[str, Any],
    ) -> None:
        """Publish a JSON message to a Kafka topic.

        Args:
            topic: Target Kafka topic.
            key: Message key (used for partitioning).
            value: Message payload as a dictionary.
        """
        value["event_timestamp"] = datetime.now(timezone.utc).isoformat()

        self._producer.produce(
            topic=topic,
            key=key.encode("utf-8"),
            value=json.dumps(value).encode("utf-8"),
            callback=self._delivery_callback,
        )
        self._producer.poll(0)  # Trigger delivery callbacks

    def publish_score_event(
        self,
        national_id_hash: str,
        score: int,
        risk_drivers: Optional[list[dict[str, Any]]] = None,
        model_version: str = "v1.0.0",
    ) -> None:
        """Publish a score computation event.

        Args:
            national_id_hash: SHA-256 hash of the customer's national ID.
            score: Computed VyceScore (300-900).
            risk_drivers: Optional list of top 3 risk drivers with SHAP values.
            model_version: Version of the model used for inference.
        """
        self._publish(
            topic=self.TOPIC_SCORES,
            key=national_id_hash,
            value={
                "national_id_hash": national_id_hash,
                "vyce_score": score,
                "risk_drivers": risk_drivers or [],
                "model_version": model_version,
            },
        )

    def publish_feature_event(
        self,
        national_id_hash: str,
        features: dict[str, float],
        feature_date: str,
    ) -> None:
        """Publish a feature computation event.

        Args:
            national_id_hash: SHA-256 hash of the customer's national ID.
            features: Dictionary of feature name to value.
            feature_date: Date the features were computed for (YYYY-MM-DD).
        """
        self._publish(
            topic=self.TOPIC_FEATURES,
            key=national_id_hash,
            value={
                "national_id_hash": national_id_hash,
                "features": features,
                "feature_date": feature_date,
            },
        )

    def publish_alert(
        self,
        alert_type: str,
        severity: str,
        message: str,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """Publish a data quality or pipeline alert.

        Args:
            alert_type: Type of alert (e.g., "data_quality", "pipeline_failure").
            severity: Alert severity ("critical", "warning", "info").
            message: Human-readable alert message.
            details: Optional additional context.
        """
        self._publish(
            topic=self.TOPIC_ALERTS,
            key=alert_type,
            value={
                "alert_type": alert_type,
                "severity": severity,
                "message": message,
                "details": details or {},
            },
        )

    def flush(self, timeout: float = 10.0) -> int:
        """Flush all buffered messages to Kafka.

        Args:
            timeout: Maximum time to wait in seconds.

        Returns:
            Number of messages still in the queue (0 means all flushed).
        """
        return self._producer.flush(timeout=timeout)
