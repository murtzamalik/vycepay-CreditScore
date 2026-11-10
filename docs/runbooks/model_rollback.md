# Model Rollback Runbook

## Overview

VyceScore uses XGBoost models for credit scoring. Models are versioned in S3 and served via the ML serving pods. This runbook covers rolling back to a previous model version.

## Model Architecture

- **Storage**: S3 bucket `{env}-vycescore-model-artifacts`
- **Path convention**: `models/{version}/xgboost_model.json`
- **Tracking**: MLflow experiment tracking
- **Serving**: ML serving pods load models at startup and cache in memory

## When to Rollback

- Model performance degradation (AUC-ROC drops below 0.75)
- Score distribution anomaly (median score shifts > 50 points)
- SHAP explanation errors
- Data drift detected by monitoring
- Regulatory concern about scoring decisions

## Pre-Rollback Checks

```bash
# 1. Check current model version in production
kubectl exec -it deploy/ml-serving -n vycescore -- \
  printenv MODEL_VERSION

# 2. Check model performance metrics
curl -sf https://api.vycescore.com/metrics | grep model_

# 3. List available model versions in S3
aws s3 ls s3://${ENV}-vycescore-model-artifacts/models/ --recursive

# 4. Check MLflow for model metrics
# Access MLflow UI or use API
```

## Rollback Procedure

### Step 1 — Identify the target model version
```bash
# List model versions with metadata
aws s3 ls s3://production-vycescore-model-artifacts/models/ \
  --recursive | sort -k1

# Check model metadata
aws s3 cp s3://production-vycescore-model-artifacts/models/<VERSION>/metadata.json - | jq .
```

### Step 2 — Update model configuration
```bash
# Option A: Update via Vault
vault kv put secret/vycescore/production/model-config \
  model_bucket="production-vycescore-model-artifacts" \
  model_path="models/<PREVIOUS_VERSION>/xgboost_model.json" \
  shap_enabled="true"

# Option B: Update via ArgoCD helm parameter
argocd app set vycescore-production \
  --helm-set-string config.MODEL_VERSION=<PREVIOUS_VERSION> \
  --grpc-web
```

### Step 3 — Restart ML serving pods
```bash
# Rolling restart to pick up new model
kubectl rollout restart deployment/ml-serving -n vycescore

# Wait for rollout
kubectl rollout status deployment/ml-serving -n vycescore --timeout=300s
```

### Step 4 — Verify rollback
```bash
# Check model version
kubectl exec -it deploy/ml-serving -n vycescore -- printenv MODEL_VERSION

# Test scoring endpoint
curl -sf -H "X-API-Key: $API_KEY" \
  https://api.vycescore.com/v1/scores/lite/test_id | jq .

# Check model metrics
curl -sf https://api.vycescore.com/metrics | grep -E "model_version|model_predictions"

# Monitor score distribution for 30 minutes
# Check Grafana dashboard: VyceScore > Model Performance
```

### Step 5 — Invalidate score cache
```bash
# If scores were cached with the bad model, flush the cache
kubectl exec -it deploy/backend-api -n vycescore -- \
  python -c "import redis; r = redis.Redis(); r.flushdb()"

# Or selectively by pattern:
kubectl exec -it deploy/backend-api -n vycescore -- \
  python -c "
import redis
r = redis.Redis()
for key in r.scan_iter('score:*'):
    r.delete(key)
print('Cache cleared')
"
```

## A/B Test Rollback

If a model is in A/B test mode:

```bash
# Set traffic to 100% previous model
argocd app set vycescore-production \
  --helm-set config.MODEL_AB_TEST_ENABLED=false \
  --helm-set config.MODEL_VERSION=<PREVIOUS_VERSION> \
  --grpc-web
argocd app sync vycescore-production --grpc-web
```

## Post-Rollback Actions

1. **Alert the data science team** about the rollback
2. **Create an incident report** documenting:
   - What model was deployed
   - When the issue was detected
   - What metrics were affected
   - Root cause analysis
3. **Review the model validation pipeline** to prevent recurrence
4. **Check if any scores need to be recalculated** for affected time window
5. **Notify partner banks** if scoring results may have been affected

## Emergency: Disable ML Scoring

If all models are compromised, disable ML scoring and return a safe default:

```bash
# Set maintenance mode — returns HTTP 503 for score requests
argocd app set vycescore-production \
  --helm-set config.SCORING_MAINTENANCE_MODE=true \
  --grpc-web
argocd app sync vycescore-production --grpc-web
```

## Contacts

| Role | Contact |
|------|---------|
| Data Science Lead | datascience@vycescore.com |
| ML Platform Engineer | mlops@vycescore.com |
| Platform Lead | platform@vycescore.com |
