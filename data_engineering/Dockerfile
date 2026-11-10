FROM apache/airflow:2.8.1-python3.11

USER root

# Install Java for PySpark
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        openjdk-17-jre-headless \
        build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV SPARK_HOME=/opt/spark
ENV PATH="${SPARK_HOME}/bin:${PATH}"

# Install Spark
ARG SPARK_VERSION=3.5.0
ARG HADOOP_VERSION=3
RUN curl -fsSL "https://archive.apache.org/dist/spark/spark-${SPARK_VERSION}/spark-${SPARK_VERSION}-bin-hadoop${HADOOP_VERSION}.tgz" \
    | tar -xz -C /opt/ && \
    mv "/opt/spark-${SPARK_VERSION}-bin-hadoop${HADOOP_VERSION}" "${SPARK_HOME}"

USER airflow

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy DAGs and jobs
COPY dags/ ${AIRFLOW_HOME}/dags/
COPY jobs/ ${AIRFLOW_HOME}/jobs/
COPY expectations/ ${AIRFLOW_HOME}/expectations/
COPY feast/ ${AIRFLOW_HOME}/feast/
COPY kafka/ ${AIRFLOW_HOME}/kafka/
COPY utils/ ${AIRFLOW_HOME}/utils/

ENV AIRFLOW__CORE__LOAD_EXAMPLES=False
ENV AIRFLOW__CORE__DAGS_FOLDER=${AIRFLOW_HOME}/dags
ENV AIRFLOW__CORE__EXECUTOR=CeleryExecutor
