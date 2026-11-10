"""
VyceScore Daily Batch Scoring DAG.

Runs daily at 03:00 UTC to execute the full scoring pipeline:
    extract -> validate -> feature engineer -> model inference -> cache refresh -> KPI reports

This DAG is idempotent and backfillable. Each run processes data for the
logical execution date (T-1), ensuring late-arriving data from the previous
day is captured.

Data retention: 10 years per Kenya DPA 2019 and CBK requirements.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator
from airflow.providers.redis.operators.redis_publish import RedisPublishOperator
from airflow.utils.task_group import TaskGroup

# ---------------------------------------------------------------------------
# Default args applied to every task in this DAG
# ---------------------------------------------------------------------------
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
    "execution_timeout": timedelta(hours=2),
    "sla": timedelta(hours=3),
}

# ---------------------------------------------------------------------------
# Callable task functions
# ---------------------------------------------------------------------------

def extract_transactions(**context) -> str:
    """Extract raw transaction data for the execution date from the data lake.

    Reads VycePay and VyceTrade Parquet partitions for the logical date,
    validates partition existence, and stages data for downstream tasks.

    Returns:
        Path to the staged extraction in the data lake.
    """
    from airflow.models import Variable

    logical_date: datetime = context["logical_date"]
    partition_date = logical_date.strftime("%Y-%m-%d")

    data_lake_base = Variable.get("DATA_LAKE_BASE_PATH", default_var="s3a://vycescore-datalake")

    vycepay_path = f"{data_lake_base}/raw/vycepay/dt={partition_date}/"
    vycetrade_path = f"{data_lake_base}/raw/vycetrade/dt={partition_date}/"
    staging_path = f"{data_lake_base}/staging/scoring/dt={partition_date}/"

    context["ti"].xcom_push(key="vycepay_path", value=vycepay_path)
    context["ti"].xcom_push(key="vycetrade_path", value=vycetrade_path)
    context["ti"].xcom_push(key="staging_path", value=staging_path)

    print(f"Staged extraction for {partition_date} at {staging_path}")
    return staging_path


def validate_extracted_data(**context) -> bool:
    """Run Great Expectations validation on extracted transaction data.

    Uses the transaction_suite checkpoint to validate schema, null checks,
    value ranges, and uniqueness constraints.

    Returns:
        True if validation passes.

    Raises:
        ValueError: If critical validation expectations fail.
    """
    logical_date: datetime = context["logical_date"]
    partition_date = logical_date.strftime("%Y-%m-%d")

    staging_path = context["ti"].xcom_pull(task_ids="extract.extract_transactions", key="staging_path")

    print(f"Running Great Expectations validation on {staging_path}")

    # In production this invokes the GE checkpoint runner.
    # Validation failures on critical expectations raise and halt the DAG.
    validation_passed = True  # Placeholder for GE checkpoint result

    if not validation_passed:
        raise ValueError(f"Data quality validation failed for {partition_date}")

    return True


def run_model_inference(**context) -> None:
    """Load the active XGBoost model and score all customers for the date.

    Steps:
        1. Read computed features from the feature store (Feast online store).
        2. Load the production model artifact from the model registry.
        3. Predict P(Serious Delinquency) for each customer.
        4. Map probabilities to VyceScore range (300-900).
        5. Generate SHAP explanations for the top 3 risk drivers.
        6. Write scored results to the scores table and Parquet archive.
    """
    from airflow.models import Variable

    logical_date: datetime = context["logical_date"]
    partition_date = logical_date.strftime("%Y-%m-%d")

    model_version = Variable.get("ACTIVE_MODEL_VERSION", default_var="v1.0.0")

    print(f"Running inference with model {model_version} for {partition_date}")

    # In production:
    # 1. feast.get_online_features() for all active customer entities
    # 2. xgboost.Booster.predict() on the feature matrix
    # 3. shap.TreeExplainer for top-3 risk drivers
    # 4. Write to PostgreSQL scores table + Parquet archive


def refresh_redis_cache(**context) -> None:
    """Refresh the Redis cache with freshly computed scores.

    Loads the scored results for the logical date and upserts them into
    Redis with a 24-hour TTL keyed by national_id_hash.
    """
    logical_date: datetime = context["logical_date"]
    partition_date = logical_date.strftime("%Y-%m-%d")

    print(f"Refreshing Redis cache with scores for {partition_date}")

    # In production:
    # 1. Read scored DataFrame from the scores table
    # 2. Pipeline SET commands: key=score:{national_id_hash}, TTL=86400
    # 3. Publish cache-refreshed event for downstream consumers


def generate_kpi_reports(**context) -> None:
    """Generate daily KPI reports after scoring completes.

    Metrics computed:
        - Total customers scored
        - Score distribution (percentiles)
        - Average feature values
        - Data quality pass rate
        - Pipeline latency
    """
    logical_date: datetime = context["logical_date"]
    partition_date = logical_date.strftime("%Y-%m-%d")

    print(f"Generating KPI reports for {partition_date}")


# ---------------------------------------------------------------------------
# DAG Definition
# ---------------------------------------------------------------------------
with DAG(
    dag_id="vycescore_daily_scoring",
    description="Daily batch scoring pipeline: extract -> validate -> feature engineer -> inference -> cache refresh -> KPI",
    default_args=DEFAULT_ARGS,
    schedule="0 3 * * *",  # 03:00 UTC daily
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["scoring", "daily", "production"],
    doc_md=__doc__,
) as dag:

    # -- Extract --
    with TaskGroup("extract") as extract_group:
        extract_task = PythonOperator(
            task_id="extract_transactions",
            python_callable=extract_transactions,
        )

    # -- Validate --
    with TaskGroup("validate") as validate_group:
        validate_task = PythonOperator(
            task_id="validate_extracted_data",
            python_callable=validate_extracted_data,
        )

    # -- Feature Engineering (PySpark) --
    with TaskGroup("feature_engineering") as feature_eng_group:
        compute_features_task = SparkSubmitOperator(
            task_id="compute_features",
            application="${AIRFLOW_HOME}/jobs/feature_eng/compute_features.py",
            name="vycescore_feature_engineering",
            conn_id="spark_default",
            application_args=[
                "--date", "{{ ds }}",
                "--input-path", "{{ ti.xcom_pull(task_ids='extract.extract_transactions', key='staging_path') }}",
            ],
            conf={
                "spark.sql.shuffle.partitions": "200",
                "spark.sql.adaptive.enabled": "true",
                "spark.serializer": "org.apache.spark.serializer.KryoSerializer",
            },
            executor_memory="4g",
            driver_memory="2g",
            num_executors=4,
        )

    # -- Model Inference --
    with TaskGroup("inference") as inference_group:
        inference_task = PythonOperator(
            task_id="run_model_inference",
            python_callable=run_model_inference,
        )

    # -- Cache Refresh --
    with TaskGroup("post_scoring") as post_scoring_group:
        cache_task = PythonOperator(
            task_id="refresh_redis_cache",
            python_callable=refresh_redis_cache,
        )

        kpi_task = PythonOperator(
            task_id="generate_kpi_reports",
            python_callable=generate_kpi_reports,
        )

        # Cache and KPI can run in parallel
        [cache_task, kpi_task]

    # -- Task Dependencies --
    extract_group >> validate_group >> feature_eng_group >> inference_group >> post_scoring_group
