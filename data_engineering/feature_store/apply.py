"""Apply (register) all Feast feature definitions.

Connects to the Feast registry and registers all entities, data sources,
and feature views defined in ``feature_definitions``.

Usage:
    python -m data_engineering.feature_store.apply
    python -m data_engineering.feature_store.apply --env production
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Any

from feast import FeatureStore, RepoConfig
from feast.infra.online_stores.redis import RedisOnlineStoreConfig
from feast.repo_config import RegistryConfig

from data_engineering.feature_store.feature_definitions import (
    ALL_ENTITIES,
    ALL_FEATURE_VIEWS,
)

logger = logging.getLogger(__name__)


def _build_config(env: str = "development") -> RepoConfig:
    """Build Feast RepoConfig for the given environment.

    Args:
        env: Environment name (development, staging, production).

    Returns:
        Configured RepoConfig.
    """
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    registry_path = os.getenv("FEAST_REGISTRY_PATH", "data/registry.db")

    config = RepoConfig(
        project="vycescore",
        provider="local",
        registry=RegistryConfig(
            registry_type="file",
            path=registry_path,
        ),
        online_store=RedisOnlineStoreConfig(
            type="redis",
            connection_string=redis_url,
        ),
        offline_store={"type": "file"},
        entity_key_serialization_version=2,
    )

    if env == "production":
        s3_registry = os.getenv(
            "FEAST_S3_REGISTRY_PATH",
            "s3://vycescore-feast/registry.db",
        )
        config.registry = RegistryConfig(
            registry_type="file",
            path=s3_registry,
        )

    return config


def apply_feature_store(env: str = "development") -> dict[str, Any]:
    """Register all Feast objects (entities + feature views).

    Args:
        env: Target environment.

    Returns:
        Summary dict with counts of registered objects.
    """
    config = _build_config(env)
    store = FeatureStore(config=config)

    logger.info(
        "Applying Feast definitions for project '%s' (env=%s)",
        config.project,
        env,
    )

    # Collect all Feast objects
    objects: list[Any] = []
    objects.extend(ALL_ENTITIES)
    objects.extend(ALL_FEATURE_VIEWS)

    store.apply(objects)

    summary = {
        "project": config.project,
        "environment": env,
        "entities_registered": len(ALL_ENTITIES),
        "feature_views_registered": len(ALL_FEATURE_VIEWS),
        "total_features": sum(
            len(fv.schema) for fv in ALL_FEATURE_VIEWS
        ),
    }

    logger.info("Feast apply complete: %s", summary)
    return summary


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Apply VyceScore Feast feature definitions"
    )
    parser.add_argument(
        "--env",
        default="development",
        choices=["development", "staging", "production"],
        help="Target environment (default: development)",
    )
    return parser.parse_args(args)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parsed = parse_args()
    result = apply_feature_store(env=parsed.env)
    print(f"Applied: {result}")
