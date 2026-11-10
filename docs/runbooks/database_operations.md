# Database Operations Runbook

## Overview

VyceScore uses Amazon RDS PostgreSQL 15 with TimescaleDB extension. This runbook covers routine operations, backup verification, migrations, and troubleshooting.

## Connection Details

| Environment | Endpoint | Port | Database |
|-------------|----------|------|----------|
| Dev | `dev-vycescore.<id>.af-south-1.rds.amazonaws.com` | 5432 | vycescore |
| Staging | `staging-vycescore.<id>.af-south-1.rds.amazonaws.com` | 5432 | vycescore |
| Production | `production-vycescore.<id>.af-south-1.rds.amazonaws.com` | 5432 | vycescore |

Credentials are stored in Vault at `secret/vycescore/{env}/db`.

### Connect via kubectl port-forward:
```bash
# Port-forward from a pod with psql
kubectl run -it --rm db-shell -n vycescore \
  --image=postgres:15 \
  --env="PGPASSWORD=$(vault kv get -field=password secret/vycescore/production/db)" \
  -- psql -h <RDS_ENDPOINT> -U vycescore_admin -d vycescore
```

## Schema Migrations

VyceScore uses Alembic for database migrations.

### Run migrations:
```bash
# Check current migration status
kubectl exec -it deploy/backend-api -n vycescore -- \
  alembic current

# Run pending migrations
kubectl exec -it deploy/backend-api -n vycescore -- \
  alembic upgrade head

# Rollback last migration
kubectl exec -it deploy/backend-api -n vycescore -- \
  alembic downgrade -1
```

### Pre-migration checklist (production):
- [ ] Migration tested in staging
- [ ] Backup taken before migration
- [ ] Migration is backward-compatible (no column drops without deprecation)
- [ ] Estimated execution time < 5 minutes (or use online migration)
- [ ] Team notified
- [ ] Rollback plan documented

## Backup Operations

### Automated backups:
- **PITR**: Continuous, retention = 30 days (production)
- **Daily snapshots**: Automated by RDS, window: 03:00-04:00 UTC
- **Cross-region replica**: Continuous replication to eu-west-1

### Manual snapshot:
```bash
aws rds create-db-snapshot \
  --db-instance-identifier production-vycescore \
  --db-snapshot-identifier "manual-$(date +%Y%m%d-%H%M%S)"
```

### List snapshots:
```bash
aws rds describe-db-snapshots \
  --db-instance-identifier production-vycescore \
  --query 'DBSnapshots[*].[DBSnapshotIdentifier,SnapshotCreateTime,Status]' \
  --output table
```

### Backup verification (monthly):
```bash
# 1. Restore latest snapshot to a test instance
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier production-vycescore-verify \
  --db-snapshot-identifier <LATEST_SNAPSHOT> \
  --db-instance-class db.t3.medium \
  --no-multi-az

# 2. Wait for availability
aws rds wait db-instance-available \
  --db-instance-identifier production-vycescore-verify

# 3. Verify data integrity
psql -h <VERIFY_ENDPOINT> -U vycescore_admin -d vycescore <<EOF
  SELECT count(*) as total_scores FROM scores;
  SELECT count(*) as total_users FROM users;
  SELECT count(*) as total_audit FROM audit_log;
  SELECT max(created_at) as latest_record FROM scores;
  -- Verify TimescaleDB
  SELECT * FROM timescaledb_information.hypertables;
EOF

# 4. Clean up
aws rds delete-db-instance \
  --db-instance-identifier production-vycescore-verify \
  --skip-final-snapshot
```

## Performance Monitoring

### Check slow queries:
```bash
# Via Performance Insights
aws pi get-resource-metrics \
  --service-type RDS \
  --identifier db-<RESOURCE_ID> \
  --metric-queries '[{"Metric": "db.SQL.tup_returned"}]' \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ)

# Via pg_stat_statements
psql -c "
SELECT
  query,
  calls,
  mean_exec_time::numeric(10,2) as avg_ms,
  total_exec_time::numeric(10,2) as total_ms,
  rows
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 20;
"
```

### Check connection count:
```bash
psql -c "
SELECT
  datname,
  state,
  count(*) as connections
FROM pg_stat_activity
GROUP BY datname, state
ORDER BY connections DESC;
"
```

### Check table sizes:
```bash
psql -c "
SELECT
  schemaname,
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size,
  pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size,
  pg_size_pretty(pg_indexes_size(schemaname||'.'||tablename)) as index_size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
LIMIT 20;
"
```

## Scaling Operations

### Vertical scaling (instance class change):
```bash
# Schedule during maintenance window
aws rds modify-db-instance \
  --db-instance-identifier production-vycescore \
  --db-instance-class db.r6g.2xlarge \
  --apply-immediately  # or --no-apply-immediately for next window

# Or via Terraform (preferred)
# Update db_instance_class in production/main.tf
terraform plan -target=module.database
terraform apply -target=module.database
```

### Storage scaling:
```bash
# RDS auto-scales storage up to max_allocated_storage.
# Check current usage:
aws cloudwatch get-metric-data --region af-south-1 \
  --metric-data-queries '[{
    "Id": "free_storage",
    "MetricStat": {
      "Metric": {
        "Namespace": "AWS/RDS",
        "MetricName": "FreeStorageSpace",
        "Dimensions": [{"Name": "DBInstanceIdentifier", "Value": "production-vycescore"}]
      },
      "Period": 300,
      "Stat": "Average"
    }
  }]' \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ)
```

## Data Retention

Per Kenya DPA 2019, VyceScore retains data for 10 years.

### Archive old data:
```bash
# Export old records to S3 (Parquet format via data engineering pipeline)
# Records older than 10 years are purged after export confirmation
psql -c "
SELECT count(*)
FROM audit_log
WHERE created_at < NOW() - INTERVAL '10 years';
"
```

### PII handling:
- PII is encrypted at rest (KMS) and in transit (TLS)
- Raw PII is anonymized after feature extraction
- Never log PII in plain text
- Access to PII requires explicit IAM role and audit trail

## Troubleshooting

### High CPU:
1. Check Performance Insights for top queries
2. Check for missing indexes: `EXPLAIN ANALYZE` on slow queries
3. Check for lock contention: `SELECT * FROM pg_locks WHERE NOT granted;`
4. Consider read replicas for read-heavy workloads

### High memory:
1. Check `shared_buffers` and `work_mem` settings
2. Look for long-running transactions: `SELECT * FROM pg_stat_activity WHERE state != 'idle' ORDER BY query_start;`
3. Check for bloated tables: `SELECT * FROM pg_stat_user_tables ORDER BY n_dead_tup DESC;`

### Replication lag (read replica):
```bash
aws cloudwatch get-metric-data --region af-south-1 \
  --metric-data-queries '[{
    "Id": "rep_lag",
    "MetricStat": {
      "Metric": {
        "Namespace": "AWS/RDS",
        "MetricName": "ReplicaLag",
        "Dimensions": [{"Name": "DBInstanceIdentifier", "Value": "production-vycescore-replica"}]
      },
      "Period": 60,
      "Stat": "Maximum"
    }
  }]' \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ)
```

## Contacts

| Role | Contact |
|------|---------|
| Database Admin | dba@vycescore.com |
| Platform Lead | platform@vycescore.com |
| AWS Support | Enterprise Support |
