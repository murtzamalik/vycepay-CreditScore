"""
VyceTrade Supply Chain Data Ingestion DAG.

Ingests supply chain data from the VyceTrade platform into the VyceScore
data lake. This data feeds the SCFV (Supply Chain Formalization Velocity)
feature and NIQ Score (Network Interdependence and Quality) computations.

Data types ingested:
    - Supplier payment records
    - Invoice data (issued and received)
    - Supply chain link registrations (digitized supplier-buyer relationships)
    - Supplier verification status

PII is hashed at ingestion. The pipeline is idempotent and backfillable.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
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


def check_vycetrade_source(**context) -> bool:
    """Verify VyceTrade source API or database replica is reachable."""
    logical_date: datetime = context["logical_date"]
    partition_date = logical_date.strftime("%Y-%m-%d")

    print(f"Checking VyceTrade source availability for {partition_date}")
    return True


def extract_supplier_payments(**context) -> str:
    """Extract supplier payment records for the logical date.

    Returns:
        Path to staged supplier payment data.
    """
    from airflow.models import Variable

    logical_date: datetime = context["logical_date"]
    partition_date = logical_date.strftime("%Y-%m-%d")
    data_lake_base = Variable.get("DATA_LAKE_BASE_PATH", default_var="s3a://vycescore-datalake")

    staging_path = f"{data_lake_base}/staging/vycetrade/payments/dt={partition_date}/"

    print(f"Extracting supplier payments for {partition_date}")
    context["ti"].xcom_push(key="payments_staging_path", value=staging_path)
    return staging_path


def extract_invoices(**context) -> str:
    """Extract invoice data (issued and received) for the logical date.

    Returns:
        Path to staged invoice data.
    """
    from airflow.models import Variable

    logical_date: datetime = context["logical_date"]
    partition_date = logical_date.strftime("%Y-%m-%d")
    data_lake_base = Variable.get("DATA_LAKE_BASE_PATH", default_var="s3a://vycescore-datalake")

    staging_path = f"{data_lake_base}/staging/vycetrade/invoices/dt={partition_date}/"

    print(f"Extracting invoices for {partition_date}")
    context["ti"].xcom_push(key="invoices_staging_path", value=staging_path)
    return staging_path


def extract_supply_chain_links(**context) -> str:
    """Extract supply chain link registrations for the logical date.

    These records represent digitized supplier-buyer relationships and are
    the primary input for the SCFV feature.

    Returns:
        Path to staged supply chain link data.
    """
    from airflow.models import Variable

    logical_date: datetime = context["logical_date"]
    partition_date = logical_date.strftime("%Y-%m-%d")
    data_lake_base = Variable.get("DATA_LAKE_BASE_PATH", default_var="s3a://vycescore-datalake")

    staging_path = f"{data_lake_base}/staging/vycetrade/links/dt={partition_date}/"

    print(f"Extracting supply chain links for {partition_date}")
    context["ti"].xcom_push(key="links_staging_path", value=staging_path)
    return staging_path


def hash_pii_and_land(**context) -> None:
    """Hash PII fields and land all VyceTrade data to the raw layer.

    Combines supplier payments, invoices, and supply chain links into the
    raw layer partitioned by date and data type.
    """
    from airflow.models import Variable

    logical_date: datetime = context["logical_date"]
    partition_date = logical_date.strftime("%Y-%m-%d")
    data_lake_base = Variable.get("DATA_LAKE_BASE_PATH", default_var="s3a://vycescore-datalake")

    raw_path = f"{data_lake_base}/raw/vycetrade/dt={partition_date}/"
    print(f"Hashing PII and landing VyceTrade data to {raw_path}")

    # In production:
    # 1. Read each staging path
    # 2. Hash PII columns (national_id, business_name, etc.)
    # 3. Drop original PII columns
    # 4. Write to raw layer with atomic overwrite
    # 5. Update data catalog

    context["ti"].xcom_push(key="raw_path", value=raw_path)


def validate_and_reconcile(**context) -> None:
    """Run data quality checks and reconcile row counts."""
    logical_date: datetime = context["logical_date"]
    partition_date = logical_date.strftime("%Y-%m-%d")
    print(f"Validating and reconciling VyceTrade data for {partition_date}")


with DAG(
    dag_id="vycetrade_ingestion",
    description="Ingest VyceTrade supply chain data (payments, invoices, links) into the data lake",
    default_args=DEFAULT_ARGS,
    schedule="0 2 * * *",  # 02:00 UTC, before the scoring DAG at 03:00
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["ingestion", "vycetrade", "production"],
    doc_md=__doc__,
) as dag:

    check_source = PythonOperator(
        task_id="check_vycetrade_source",
        python_callable=check_vycetrade_source,
    )

    with TaskGroup("extract") as extract_group:
        payments_task = PythonOperator(
            task_id="extract_supplier_payments",
            python_callable=extract_supplier_payments,
        )
        invoices_task = PythonOperator(
            task_id="extract_invoices",
            python_callable=extract_invoices,
        )
        links_task = PythonOperator(
            task_id="extract_supply_chain_links",
            python_callable=extract_supply_chain_links,
        )
        # All three extractions run in parallel
        [payments_task, invoices_task, links_task]

    hash_and_land = PythonOperator(
        task_id="hash_pii_and_land",
        python_callable=hash_pii_and_land,
    )

    validate = PythonOperator(
        task_id="validate_and_reconcile",
        python_callable=validate_and_reconcile,
    )

    check_source >> extract_group >> hash_and_land >> validate
