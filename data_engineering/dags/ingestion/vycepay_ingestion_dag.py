"""
VycePay Transaction Data Ingestion DAG.

Ingests raw transaction data from the VycePay platform into the VyceScore
data lake. Handles:
    - Fund Transfers (FT) and Inter-Bank Fund Transfers (IBFT)
    - Remittance transactions
    - Merchant activity records

Data is landed as Parquet files partitioned by date in the raw layer of
the data lake. PII fields (national_id, phone, name) are hashed at
ingestion time using SHA-256 with a configured salt.

The DAG is idempotent: re-running for the same date overwrites the
partition, producing identical output for identical input.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator
from airflow.sensors.external_task import ExternalTaskSensor
from airflow.utils.task_group import TaskGroup

DEFAULT_ARGS: dict = {
    "owner": "vycescore-data-eng",
    "depends_on_past": False,
    "email": ["data-eng@vycepay.com"],
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=30),
    "execution_timeout": timedelta(hours=1),
    "sla": timedelta(hours=2),
}


def check_source_availability(**context) -> bool:
    """Verify VycePay source database/API is reachable and data is available.

    Returns:
        True if the source is available and the partition has data.

    Raises:
        ConnectionError: If the VycePay source cannot be reached.
    """
    logical_date: datetime = context["logical_date"]
    partition_date = logical_date.strftime("%Y-%m-%d")

    print(f"Checking VycePay source availability for {partition_date}")
    # In production: test connection to VycePay DB replica or API
    return True


def extract_vycepay_transactions(**context) -> str:
    """Extract VycePay transactions for the logical date.

    Reads from the VycePay database replica and writes raw JSON/CSV
    to a staging area before Parquet conversion.

    Transaction types extracted:
        - FT (Fund Transfer)
        - IBFT (Inter-Bank Fund Transfer)
        - REMIT (Remittance)
        - MERCHANT (Merchant payments)

    Returns:
        Path to staged raw data.
    """
    from airflow.models import Variable

    logical_date: datetime = context["logical_date"]
    partition_date = logical_date.strftime("%Y-%m-%d")
    data_lake_base = Variable.get("DATA_LAKE_BASE_PATH", default_var="s3a://vycescore-datalake")

    staging_path = f"{data_lake_base}/staging/vycepay/dt={partition_date}/"

    print(f"Extracting VycePay transactions for {partition_date} to {staging_path}")

    # In production:
    # 1. Connect to VycePay DB replica (read-only)
    # 2. SELECT transactions WHERE date = partition_date
    # 3. Write to staging as Parquet with snappy compression
    # 4. Record row count for reconciliation

    context["ti"].xcom_push(key="staging_path", value=staging_path)
    context["ti"].xcom_push(key="row_count", value=0)  # Placeholder
    return staging_path


def hash_pii_fields(**context) -> None:
    """Hash PII fields in the staged data before landing in the raw layer.

    Fields hashed:
        - national_id -> national_id_hash
        - phone_number -> phone_hash
        - full_name -> name_hash

    Uses SHA-256 with a configurable salt (VYCESCORE_PII_SALT env var).
    Original PII fields are dropped after hashing.
    """
    staging_path = context["ti"].xcom_pull(
        task_ids="extract.extract_vycepay_transactions",
        key="staging_path",
    )
    print(f"Hashing PII fields in {staging_path}")

    # In production:
    # 1. Read staged Parquet
    # 2. Apply SHA-256(salt + field) for each PII column
    # 3. Drop original PII columns
    # 4. Write back to staging


def land_to_raw_layer(**context) -> str:
    """Move validated, PII-hashed data from staging to the raw layer.

    The raw layer is the immutable, append-only historical record.
    Partitioned by dt=YYYY-MM-DD.

    Returns:
        Path to the raw layer partition.
    """
    from airflow.models import Variable

    logical_date: datetime = context["logical_date"]
    partition_date = logical_date.strftime("%Y-%m-%d")
    data_lake_base = Variable.get("DATA_LAKE_BASE_PATH", default_var="s3a://vycescore-datalake")

    raw_path = f"{data_lake_base}/raw/vycepay/dt={partition_date}/"

    print(f"Landing data to raw layer: {raw_path}")

    # In production:
    # 1. Copy from staging to raw (atomic overwrite for idempotency)
    # 2. Write _SUCCESS sentinel file
    # 3. Update data catalog / Hive metastore partition

    context["ti"].xcom_push(key="raw_path", value=raw_path)
    return raw_path


def reconcile_counts(**context) -> None:
    """Compare source row count with landed row count for data integrity."""
    source_count = context["ti"].xcom_pull(
        task_ids="extract.extract_vycepay_transactions",
        key="row_count",
    )
    print(f"Reconciliation: source={source_count} rows")

    # In production:
    # 1. Count rows in raw partition
    # 2. Compare with source count
    # 3. Alert if mismatch > threshold (0.1%)


with DAG(
    dag_id="vycepay_ingestion",
    description="Ingest VycePay transaction data (FT, IBFT, remittance, merchant) into the data lake",
    default_args=DEFAULT_ARGS,
    schedule="30 1 * * *",  # 01:30 UTC, before the scoring DAG at 03:00
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["ingestion", "vycepay", "production"],
    doc_md=__doc__,
) as dag:

    with TaskGroup("source_check") as source_check_group:
        check_source = PythonOperator(
            task_id="check_source_availability",
            python_callable=check_source_availability,
        )

    with TaskGroup("extract") as extract_group:
        extract_task = PythonOperator(
            task_id="extract_vycepay_transactions",
            python_callable=extract_vycepay_transactions,
        )

    with TaskGroup("transform") as transform_group:
        hash_pii = PythonOperator(
            task_id="hash_pii_fields",
            python_callable=hash_pii_fields,
        )

    with TaskGroup("load") as load_group:
        land_raw = PythonOperator(
            task_id="land_to_raw_layer",
            python_callable=land_to_raw_layer,
        )

    with TaskGroup("quality") as quality_group:
        reconcile = PythonOperator(
            task_id="reconcile_counts",
            python_callable=reconcile_counts,
        )

    source_check_group >> extract_group >> transform_group >> load_group >> quality_group
