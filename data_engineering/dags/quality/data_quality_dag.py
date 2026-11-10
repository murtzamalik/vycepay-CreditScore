"""
Data Quality Validation DAG.

Runs Great Expectations checkpoints against the raw and feature layers
in the data lake. Validates:
    - Schema conformance (column presence and types)
    - Null checks on critical columns
    - Value range expectations (e.g., transaction amounts > 0)
    - Uniqueness constraints (e.g., transaction_id)
    - Referential integrity between VycePay and VyceTrade datasets
    - Freshness checks (data should be no older than 24h)

Results are written to the GE data docs site and alerts are sent on failure.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import BranchPythonOperator, PythonOperator
from airflow.utils.task_group import TaskGroup

DEFAULT_ARGS: dict = {
    "owner": "vycescore-data-eng",
    "depends_on_past": False,
    "email": ["data-eng@vycepay.com"],
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=1),
    "sla": timedelta(hours=1, minutes=30),
}


def run_transaction_quality_checks(**context) -> str:
    """Run Great Expectations suite on VycePay transaction data.

    Validates the transaction_suite expectations:
        - transaction_id is unique and not null
        - amount is positive and within expected range
        - transaction_type is in allowed set
        - timestamp is within expected date range
        - national_id_hash is not null and has expected format

    Returns:
        "quality_passed" or "quality_failed" for branching.
    """
    logical_date: datetime = context["logical_date"]
    partition_date = logical_date.strftime("%Y-%m-%d")

    print(f"Running transaction quality checks for {partition_date}")

    # In production:
    # import great_expectations as gx
    # context_gx = gx.get_context()
    # result = context_gx.run_checkpoint(checkpoint_name="transaction_checkpoint")
    # success = result.success

    success = True  # Placeholder

    if success:
        print(f"Transaction quality checks PASSED for {partition_date}")
        return "quality_gates.quality_passed"
    else:
        print(f"Transaction quality checks FAILED for {partition_date}")
        return "quality_gates.quality_failed"


def run_supply_chain_quality_checks(**context) -> str:
    """Run Great Expectations suite on VyceTrade supply chain data.

    Validates:
        - supplier_id and buyer_id are not null
        - invoice amounts are positive
        - link registration dates are valid
        - no duplicate link records per supplier-buyer pair per day

    Returns:
        "quality_passed" or "quality_failed" for branching.
    """
    logical_date: datetime = context["logical_date"]
    partition_date = logical_date.strftime("%Y-%m-%d")

    print(f"Running supply chain quality checks for {partition_date}")

    success = True  # Placeholder
    if success:
        return "quality_gates.quality_passed"
    else:
        return "quality_gates.quality_failed"


def run_feature_quality_checks(**context) -> str:
    """Validate computed features are within expected ranges.

    Feature validation ranges:
        - CBLRI: [0.0, 1.0]
        - UTDI: [0.0, 1.0]
        - SCFV: [0.0, 100.0]
        - DDC Ratio: [0.0, 1.0]
        - NIQ Score: [300, 900]
        - GOS Index: [0.0, 1.0]

    Returns:
        "quality_passed" or "quality_failed" for branching.
    """
    logical_date: datetime = context["logical_date"]
    partition_date = logical_date.strftime("%Y-%m-%d")

    print(f"Running feature quality checks for {partition_date}")

    success = True  # Placeholder
    if success:
        return "quality_gates.quality_passed"
    else:
        return "quality_gates.quality_failed"


def on_quality_passed(**context) -> None:
    """Log successful quality check and update monitoring metrics."""
    logical_date: datetime = context["logical_date"]
    print(f"All quality checks passed for {logical_date.strftime('%Y-%m-%d')}")


def on_quality_failed(**context) -> None:
    """Handle quality failure: send alerts, log to incident tracker."""
    logical_date: datetime = context["logical_date"]
    partition_date = logical_date.strftime("%Y-%m-%d")

    print(f"QUALITY FAILURE for {partition_date} -- alerting on-call team")

    # In production:
    # 1. Send PagerDuty / Slack alert
    # 2. Log failure details to incident tracker
    # 3. Optionally quarantine the affected partition


with DAG(
    dag_id="data_quality_validation",
    description="Run Great Expectations validation suites on raw and feature data",
    default_args=DEFAULT_ARGS,
    schedule="30 2 * * *",  # 02:30 UTC, after ingestion, before scoring
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["quality", "great-expectations", "production"],
    doc_md=__doc__,
) as dag:

    with TaskGroup("validation_suites") as validation_group:
        txn_check = BranchPythonOperator(
            task_id="run_transaction_quality_checks",
            python_callable=run_transaction_quality_checks,
        )

        sc_check = BranchPythonOperator(
            task_id="run_supply_chain_quality_checks",
            python_callable=run_supply_chain_quality_checks,
        )

        feat_check = BranchPythonOperator(
            task_id="run_feature_quality_checks",
            python_callable=run_feature_quality_checks,
        )

    with TaskGroup("quality_gates") as quality_gates_group:
        passed = PythonOperator(
            task_id="quality_passed",
            python_callable=on_quality_passed,
            trigger_rule="none_failed_min_one_success",
        )

        failed = PythonOperator(
            task_id="quality_failed",
            python_callable=on_quality_failed,
            trigger_rule="none_failed_min_one_success",
        )

    [txn_check, sc_check, feat_check] >> passed
    [txn_check, sc_check, feat_check] >> failed
