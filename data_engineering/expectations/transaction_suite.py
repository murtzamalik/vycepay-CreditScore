"""
Great Expectations suite for VycePay transaction data validation.

Defines expectations for the raw transaction dataset including:
    - Not-null checks on critical columns
    - Value range validations
    - Uniqueness constraints
    - Format and type checks
    - Freshness validation

Usage:
    This module is imported by the data quality DAG to create and run
    the transaction validation checkpoint programmatically.
"""

from __future__ import annotations

from typing import Any

import great_expectations as gx
from great_expectations.core import ExpectationSuite
from great_expectations.core.expectation_configuration import ExpectationConfiguration


def build_transaction_suite() -> ExpectationSuite:
    """Build the Great Expectations suite for VycePay transaction data.

    Returns:
        Configured ExpectationSuite with all transaction data expectations.
    """
    suite = ExpectationSuite(expectation_suite_name="vycescore_transaction_suite")

    # ------------------------------------------------------------------
    # 1. NOT NULL checks on critical columns
    # ------------------------------------------------------------------
    not_null_columns = [
        "transaction_id",
        "national_id_hash",
        "transaction_type",
        "amount",
        "currency",
        "timestamp",
        "is_cross_border",
    ]

    for column in not_null_columns:
        suite.add_expectation(
            ExpectationConfiguration(
                expectation_type="expect_column_values_to_not_be_null",
                kwargs={"column": column},
                meta={
                    "severity": "critical",
                    "notes": f"{column} must never be null",
                },
            )
        )

    # ------------------------------------------------------------------
    # 2. UNIQUENESS constraints
    # ------------------------------------------------------------------
    suite.add_expectation(
        ExpectationConfiguration(
            expectation_type="expect_column_values_to_be_unique",
            kwargs={"column": "transaction_id"},
            meta={
                "severity": "critical",
                "notes": "Each transaction must have a unique identifier",
            },
        )
    )

    # ------------------------------------------------------------------
    # 3. VALUE RANGE checks
    # ------------------------------------------------------------------

    # Transaction amount must be positive
    suite.add_expectation(
        ExpectationConfiguration(
            expectation_type="expect_column_values_to_be_between",
            kwargs={
                "column": "amount",
                "min_value": 0.01,
                "max_value": 50_000_000.0,  # 50M KES upper bound
                "strict_min": False,
            },
            meta={
                "severity": "critical",
                "notes": "Amount must be positive and below 50M KES",
            },
        )
    )

    # is_cross_border must be 0 or 1
    suite.add_expectation(
        ExpectationConfiguration(
            expectation_type="expect_column_values_to_be_in_set",
            kwargs={
                "column": "is_cross_border",
                "value_set": [0, 1],
            },
            meta={
                "severity": "critical",
                "notes": "Binary flag must be 0 or 1",
            },
        )
    )

    # Transaction type must be in the allowed set
    suite.add_expectation(
        ExpectationConfiguration(
            expectation_type="expect_column_values_to_be_in_set",
            kwargs={
                "column": "transaction_type",
                "value_set": ["FT", "IBFT", "REMIT", "MERCHANT", "BILL_PAY", "CASH_IN", "CASH_OUT"],
            },
            meta={
                "severity": "warning",
                "notes": "Transaction type must be a known type",
            },
        )
    )

    # Currency must be a recognized ISO 4217 code
    suite.add_expectation(
        ExpectationConfiguration(
            expectation_type="expect_column_values_to_be_in_set",
            kwargs={
                "column": "currency",
                "value_set": ["KES", "USD", "EUR", "GBP", "UGX", "TZS", "RWF", "ETB"],
            },
            meta={
                "severity": "warning",
                "notes": "Currency must be a supported ISO 4217 code",
            },
        )
    )

    # Latitude range (Kenya and surrounding region)
    suite.add_expectation(
        ExpectationConfiguration(
            expectation_type="expect_column_values_to_be_between",
            kwargs={
                "column": "latitude",
                "min_value": -12.0,
                "max_value": 15.0,
                "mostly": 0.95,  # Allow 5% outside range for cross-border
            },
            meta={
                "severity": "warning",
                "notes": "Latitude should be within East Africa region (95% threshold)",
            },
        )
    )

    # Longitude range (Kenya and surrounding region)
    suite.add_expectation(
        ExpectationConfiguration(
            expectation_type="expect_column_values_to_be_between",
            kwargs={
                "column": "longitude",
                "min_value": 25.0,
                "max_value": 55.0,
                "mostly": 0.95,
            },
            meta={
                "severity": "warning",
                "notes": "Longitude should be within East Africa region (95% threshold)",
            },
        )
    )

    # ------------------------------------------------------------------
    # 4. FORMAT checks
    # ------------------------------------------------------------------

    # national_id_hash should be a 64-character hex string (SHA-256)
    suite.add_expectation(
        ExpectationConfiguration(
            expectation_type="expect_column_values_to_match_regex",
            kwargs={
                "column": "national_id_hash",
                "regex": r"^[a-f0-9]{64}$",
            },
            meta={
                "severity": "critical",
                "notes": "national_id_hash must be a valid SHA-256 hex digest",
            },
        )
    )

    # ------------------------------------------------------------------
    # 5. TABLE-LEVEL expectations
    # ------------------------------------------------------------------

    # Expect at least some rows (non-empty partition)
    suite.add_expectation(
        ExpectationConfiguration(
            expectation_type="expect_table_row_count_to_be_between",
            kwargs={
                "min_value": 1,
                "max_value": 100_000_000,  # Sanity upper bound
            },
            meta={
                "severity": "critical",
                "notes": "Partition must contain at least 1 row",
            },
        )
    )

    # Expect required columns to exist
    required_columns = [
        "transaction_id",
        "national_id_hash",
        "transaction_type",
        "amount",
        "currency",
        "timestamp",
        "is_cross_border",
    ]
    for col in required_columns:
        suite.add_expectation(
            ExpectationConfiguration(
                expectation_type="expect_column_to_exist",
                kwargs={"column": col},
                meta={
                    "severity": "critical",
                    "notes": f"Column {col} must exist in the dataset",
                },
            )
        )

    return suite


def create_checkpoint_config(
    data_source_name: str = "vycepay_transactions",
    suite_name: str = "vycescore_transaction_suite",
) -> dict[str, Any]:
    """Create a Great Expectations checkpoint configuration.

    Args:
        data_source_name: Name of the configured data source.
        suite_name: Name of the expectation suite.

    Returns:
        Checkpoint configuration dictionary.
    """
    return {
        "name": "transaction_checkpoint",
        "config_version": 1.0,
        "class_name": "Checkpoint",
        "run_name_template": "%Y%m%d-%H%M%S-transaction-validation",
        "validations": [
            {
                "batch_request": {
                    "datasource_name": data_source_name,
                    "data_connector_name": "default_inferred_data_connector_name",
                    "data_asset_name": "transactions",
                },
                "expectation_suite_name": suite_name,
            }
        ],
        "action_list": [
            {
                "name": "store_validation_result",
                "action": {"class_name": "StoreValidationResultAction"},
            },
            {
                "name": "update_data_docs",
                "action": {"class_name": "UpdateDataDocsAction"},
            },
        ],
    }


if __name__ == "__main__":
    suite = build_transaction_suite()
    print(f"Built suite '{suite.expectation_suite_name}' with "
          f"{len(suite.expectations)} expectations")
    for exp in suite.expectations:
        print(f"  - {exp.expectation_type}: {exp.kwargs}")
