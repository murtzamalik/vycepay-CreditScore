"""
Feast Feature Repository configuration for VyceScore.

Defines the Feast project, provider, and registry settings.
This is the entry point for `feast apply` and `feast materialize`.

Provider: local (development) or aws/gcp (production).
Online store: Redis for low-latency serving (<10ms).
Offline store: File-based (dev) or Redshift/BigQuery (prod).
Registry: File-based (dev) or S3/GCS (prod).
"""

from __future__ import annotations

from datetime import timedelta

from feast import FeatureStore, RepoConfig
from feast.infra.online_stores.redis import RedisOnlineStoreConfig
from feast.repo_config import RegistryConfig

# ---------------------------------------------------------------------------
# Repository configuration
# ---------------------------------------------------------------------------

REPO_CONFIG = RepoConfig(
    project="vycescore",
    provider="local",
    registry=RegistryConfig(
        registry_type="file",
        path="data/registry.db",
    ),
    online_store=RedisOnlineStoreConfig(
        type="redis",
        connection_string="redis://localhost:6379",
    ),
    offline_store={
        "type": "file",
    },
    entity_key_serialization_version=2,
)


def get_feature_store() -> FeatureStore:
    """Create and return a configured Feast FeatureStore instance.

    Returns:
        FeatureStore configured for the VyceScore project.
    """
    return FeatureStore(config=REPO_CONFIG)


if __name__ == "__main__":
    store = get_feature_store()
    print(f"Feast project: {store.project}")
    print(f"Provider: {store.config.provider}")
    print(f"Online store: {store.config.online_store}")
