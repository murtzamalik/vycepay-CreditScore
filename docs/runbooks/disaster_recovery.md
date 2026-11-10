# Disaster Recovery Runbook

## Overview

VyceScore DR strategy covers regional failure, data corruption, and infrastructure loss scenarios. Recovery targets:

| Metric | Target |
|--------|--------|
| RPO (Recovery Point Objective) | < 1 hour (PITR for database) |
| RTO (Recovery Time Objective) | < 4 hours (regional failover) |
| API Availability SLA | 99.9% |

## Infrastructure Inventory

| Component | Primary Region | DR Region | Replication |
|-----------|---------------|-----------|-------------|
| EKS Cluster | af-south-1 | eu-west-1 | Cold standby (Terraform) |
| RDS PostgreSQL | af-south-1 (Multi-AZ) | eu-west-1 (Cross-region replica) |
| ElastiCache Redis | af-south-1 (Multi-AZ) | eu-west-1 (Rebuild from RDS) |
| S3 Buckets | af-south-1 | eu-west-1 (CRR enabled) |
| MSK Kafka | af-south-1 | eu-west-1 (Rebuild, replay from S3) |

## Scenario 1: Single AZ Failure

**Impact**: Partial service degradation, automatic recovery.

**Response**: No manual action required.
- RDS Multi-AZ failover is automatic (< 2 minutes)
- ElastiCache failover is automatic with multi-AZ enabled
- EKS pods redistribute to healthy AZ via pod anti-affinity

**Verification**:
```bash
# Check RDS failover status
aws rds describe-db-instances --db-instance-identifier production-vycescore \
  --query 'DBInstances[0].[AvailabilityZone,MultiAZ,StatusInfos]'

# Check ElastiCache status
aws elasticache describe-replication-groups \
  --replication-group-id production-vycescore

# Check pod distribution
kubectl get pods -n vycescore -o wide
```

## Scenario 2: Regional Failure (Full DR Failover)

**Impact**: Complete service outage in primary region.

### Step 1 — Confirm regional outage
```bash
# Check AWS health dashboard
aws health describe-events --region af-south-1

# Verify primary cluster is unreachable
aws eks describe-cluster --name production-vycescore --region af-south-1
```

### Step 2 — Promote RDS read replica to primary
```bash
# Promote the cross-region read replica
aws rds promote-read-replica \
  --db-instance-identifier production-vycescore-replica \
  --region eu-west-1

# Wait for promotion (typically 5-10 minutes)
aws rds wait db-instance-available \
  --db-instance-identifier production-vycescore-replica \
  --region eu-west-1
```

### Step 3 — Deploy EKS cluster in DR region
```bash
cd infrastructure/terraform/environments/production

# Switch to DR region
export AWS_DEFAULT_REGION=eu-west-1

# Apply with DR overrides
terraform init -reconfigure \
  -backend-config="key=production-dr/terraform.tfstate" \
  -backend-config="region=eu-west-1"

terraform apply \
  -var="aws_region=eu-west-1" \
  -var="vpc_cidr=10.30.0.0/16"
```

### Step 4 — Deploy application to DR cluster
```bash
# Configure kubectl for DR cluster
aws eks update-kubeconfig --name production-vycescore --region eu-west-1

# Deploy via Helm
helm upgrade --install vycescore infrastructure/helm/vycescore \
  -n vycescore --create-namespace \
  -f infrastructure/helm/vycescore/values.yaml \
  -f infrastructure/helm/vycescore/values-prod.yaml \
  --set config.DB_HOST=<DR_RDS_ENDPOINT>
```

### Step 5 — Update DNS
```bash
# Switch Route53 to DR region
aws route53 change-resource-record-sets \
  --hosted-zone-id <ZONE_ID> \
  --change-batch '{
    "Changes": [{
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "api.vycescore.com",
        "Type": "A",
        "AliasTarget": {
          "HostedZoneId": "<DR_ALB_ZONE_ID>",
          "DNSName": "<DR_ALB_DNS>",
          "EvaluateTargetHealth": true
        }
      }
    }]
  }'
```

### Step 6 — Verify DR environment
```bash
curl -sf https://api.vycescore.com/health | jq .
curl -sf https://api.vycescore.com/v1/health | jq .
```

## Scenario 3: Database Corruption

### Point-in-Time Recovery (PITR)
```bash
# Restore to a specific timestamp
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier production-vycescore \
  --target-db-instance-identifier production-vycescore-pitr \
  --restore-time "2026-03-08T12:00:00Z" \
  --db-instance-class db.r6g.xlarge \
  --multi-az \
  --region af-south-1

# Wait for restore
aws rds wait db-instance-available \
  --db-instance-identifier production-vycescore-pitr

# Verify data integrity
psql -h <PITR_ENDPOINT> -U vycescore_admin -d vycescore \
  -c "SELECT count(*) FROM scores; SELECT count(*) FROM audit_log;"

# Swap endpoints — update application config
vault kv put secret/vycescore/production/db \
  host="<PITR_ENDPOINT>" \
  port="5432" \
  name="vycescore" \
  username="vycescore_admin" \
  password="<PASSWORD>"

# Restart application pods
kubectl rollout restart deployment -n vycescore
```

### Restore from snapshot
```bash
# List available snapshots
aws rds describe-db-snapshots \
  --db-instance-identifier production-vycescore \
  --query 'DBSnapshots[*].[DBSnapshotIdentifier,SnapshotCreateTime]' \
  --output table

# Restore from snapshot
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier production-vycescore-restored \
  --db-snapshot-identifier <SNAPSHOT_ID> \
  --db-instance-class db.r6g.xlarge \
  --multi-az
```

## Scenario 4: Redis Cache Loss

Redis is a cache layer. Loss of Redis data is recoverable:

```bash
# 1. Check ElastiCache status
aws elasticache describe-replication-groups \
  --replication-group-id production-vycescore

# 2. If cluster is healthy but data lost, scores will be re-cached on demand
# No action needed — cache miss triggers fresh computation from DB

# 3. If cluster is unhealthy, create a new one via Terraform
cd infrastructure/terraform/environments/production
terraform apply -target=module.database

# 4. Force batch re-computation to warm the cache
kubectl exec -it deploy/worker -n vycescore -- \
  python -m app.batch.recalculate --force
```

## Communication Plan

| Time | Action |
|------|--------|
| T+0 min | Incident detected — on-call engineer paged |
| T+5 min | Incident confirmed — status page updated |
| T+15 min | Initial assessment — partner banks notified |
| T+30 min | Recovery plan communicated |
| T+4 hours | RTO target — service restored |
| T+24 hours | Post-incident review |

## DR Test Schedule

| Test | Frequency | Duration |
|------|-----------|----------|
| RDS failover test | Quarterly | 30 minutes |
| Cross-region replica promotion | Semi-annual | 2 hours |
| Full DR failover | Annual | 4 hours |
| Backup restoration | Monthly | 1 hour |

## Contacts

| Role | Contact |
|------|---------|
| Incident Commander | oncall@vycescore.com |
| Platform Lead | platform@vycescore.com |
| Database Admin | dba@vycescore.com |
| AWS Support | Enterprise Support (Severity 1) |
