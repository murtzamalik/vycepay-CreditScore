"""
Feast Entity definition for VyceScore customers.

The primary entity is the customer, identified by their hashed national ID.
All feature views join on this entity to produce the scoring feature vector.

PII is never stored in the feature store -- only the SHA-256 hash of the
national ID is used as the entity key.
"""

from __future__ import annotations

from feast import Entity, ValueType

# ---------------------------------------------------------------------------
# Customer Entity
# ---------------------------------------------------------------------------

customer = Entity(
    name="customer",
    join_keys=["national_id_hash"],
    value_type=ValueType.STRING,
    description=(
        "VyceScore customer entity, identified by SHA-256 hash of national ID. "
        "All scoring features are keyed on this entity."
    ),
    tags={
        "owner": "vycescore-data-eng",
        "pii": "false",
        "source": "vycepay,vycetrade",
    },
)
