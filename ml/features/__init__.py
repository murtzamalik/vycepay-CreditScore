"""VyceScore feature engineering package.

Contains definitions for the six core scoring features, transaction,
network, supply chain, and compliance feature modules, plus the
FeatureRegistry for cataloging all available features.
"""

from __future__ import annotations

from typing import Iterator

from ml.features.base import (
    BaseFeatureComputer,
    FeatureCategory,
    FeatureMetadata,
    FeatureResult,
)
from ml.features.compliance_features import ALL_COMPLIANCE_FEATURES
from ml.features.core_features import ALL_CORE_FEATURES
from ml.features.network_features import ALL_NETWORK_FEATURES
from ml.features.supply_chain_features import ALL_SUPPLY_CHAIN_FEATURES
from ml.features.transaction_features import ALL_TRANSACTION_FEATURES


class FeatureRegistry:
    """Central catalog of all available feature computers.

    Supports registration, lookup by name or category, and bulk
    instantiation for pipeline orchestration.

    Usage::

        registry = FeatureRegistry()
        registry.register_defaults()

        # Get a specific computer
        computer = registry.get("tx_volume_30d")
        result = computer.compute(df)

        # Iterate all features in a category
        for computer in registry.by_category(FeatureCategory.TRANSACTION):
            result = computer.compute(df)
    """

    def __init__(self) -> None:
        self._registry: dict[str, BaseFeatureComputer] = {}

    def register(self, computer: BaseFeatureComputer) -> None:
        """Register a feature computer instance."""
        name = computer.metadata.name
        if name in self._registry:
            raise ValueError(
                f"Feature '{name}' is already registered. "
                "Use replace() to overwrite."
            )
        self._registry[name] = computer

    def replace(self, computer: BaseFeatureComputer) -> None:
        """Register or replace a feature computer instance."""
        self._registry[computer.metadata.name] = computer

    def get(self, name: str) -> BaseFeatureComputer:
        """Retrieve a registered feature computer by name.

        Raises:
            KeyError: If the feature name is not registered.
        """
        if name not in self._registry:
            raise KeyError(
                f"Feature '{name}' not found. "
                f"Available: {sorted(self._registry.keys())}"
            )
        return self._registry[name]

    def by_category(
        self, category: FeatureCategory
    ) -> list[BaseFeatureComputer]:
        """Return all feature computers in a given category."""
        return [
            c for c in self._registry.values()
            if c.metadata.category == category
        ]

    def all_features(self) -> list[BaseFeatureComputer]:
        """Return all registered feature computers."""
        return list(self._registry.values())

    def feature_names(self) -> list[str]:
        """Return sorted list of all registered feature names."""
        return sorted(self._registry.keys())

    def __len__(self) -> int:
        return len(self._registry)

    def __contains__(self, name: str) -> bool:
        return name in self._registry

    def __iter__(self) -> Iterator[BaseFeatureComputer]:
        return iter(self._registry.values())

    def register_defaults(self) -> None:
        """Register all built-in feature computers.

        Registers transaction, network, supply chain, compliance,
        and core features.
        """
        all_classes: list[type[BaseFeatureComputer]] = [
            *ALL_TRANSACTION_FEATURES,
            *ALL_NETWORK_FEATURES,
            *ALL_SUPPLY_CHAIN_FEATURES,
            *ALL_COMPLIANCE_FEATURES,
            *ALL_CORE_FEATURES,
        ]
        for cls in all_classes:
            instance = cls()
            if instance.metadata.name not in self._registry:
                self._registry[instance.metadata.name] = instance

    def metadata_table(self) -> list[dict[str, str]]:
        """Return a list of dicts summarizing all registered features.

        Useful for documentation and debugging.
        """
        rows: list[dict[str, str]] = []
        for computer in self._registry.values():
            meta = computer.metadata
            rows.append({
                "name": meta.name,
                "category": meta.category.value,
                "description": meta.description,
                "unit": meta.unit,
                "value_range": str(meta.value_range),
            })
        return rows


def create_default_registry() -> FeatureRegistry:
    """Create and return a FeatureRegistry with all built-in features."""
    registry = FeatureRegistry()
    registry.register_defaults()
    return registry


__all__ = [
    "BaseFeatureComputer",
    "FeatureCategory",
    "FeatureMetadata",
    "FeatureRegistry",
    "FeatureResult",
    "create_default_registry",
]
