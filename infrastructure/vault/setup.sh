#!/usr/bin/env bash
###############################################################################
# VyceScore — Vault Bootstrap Script
# Configures Kubernetes auth, secret engines, policies, and roles.
#
# Prerequisites:
#   - Vault is initialized and unsealed
#   - VAULT_ADDR and VAULT_TOKEN are set
#   - kubectl is configured for the target cluster
#
# Usage: ./setup.sh <environment>  (dev|staging|production)
###############################################################################
set -euo pipefail

ENV="${1:?Usage: $0 <environment> (dev|staging|production)}"

if [[ ! "$ENV" =~ ^(dev|staging|production)$ ]]; then
  echo "ERROR: Invalid environment '$ENV'. Must be dev, staging, or production."
  exit 1
fi

echo "=== VyceScore Vault Setup for '$ENV' ==="

# ---------------------------------------------------------------------------
# 1. Enable KV v2 secret engine
# ---------------------------------------------------------------------------
echo "[1/5] Enabling KV v2 secret engine..."
vault secrets enable -path=secret -version=2 kv 2>/dev/null || \
  echo "  KV v2 already enabled at secret/"

# ---------------------------------------------------------------------------
# 2. Write initial secrets (placeholders — replace with real values)
# ---------------------------------------------------------------------------
echo "[2/5] Writing placeholder secrets for $ENV..."

vault kv put "secret/vycescore/$ENV/db" \
  host="REPLACE_WITH_RDS_ENDPOINT" \
  port="5432" \
  name="vycescore" \
  username="REPLACE_WITH_DB_USERNAME" \
  password="REPLACE_WITH_DB_PASSWORD" \
  ssl_mode="require"

vault kv put "secret/vycescore/$ENV/redis" \
  host="REPLACE_WITH_REDIS_ENDPOINT" \
  port="6379" \
  auth_token="REPLACE_WITH_REDIS_AUTH_TOKEN" \
  ssl="true" \
  db="0"

vault kv put "secret/vycescore/$ENV/api-keys" \
  master_key="REPLACE_WITH_API_MASTER_KEY" \
  jwt_secret="REPLACE_WITH_JWT_SECRET"

vault kv put "secret/vycescore/$ENV/kafka" \
  bootstrap_servers="REPLACE_WITH_MSK_BOOTSTRAP" \
  security_protocol="SASL_SSL" \
  sasl_mechanism="AWS_MSK_IAM"

vault kv put "secret/vycescore/$ENV/compliance/smile-id" \
  api_key="REPLACE_WITH_SMILE_ID_KEY" \
  partner_id="REPLACE_WITH_PARTNER_ID"

vault kv put "secret/vycescore/$ENV/compliance/comply-advantage" \
  api_key="REPLACE_WITH_COMPLY_ADVANTAGE_KEY"

vault kv put "secret/vycescore/$ENV/model-config" \
  model_bucket="$ENV-vycescore-model-artifacts" \
  model_path="models/latest/xgboost_model.json" \
  shap_enabled="true"

# ---------------------------------------------------------------------------
# 3. Write policies
# ---------------------------------------------------------------------------
echo "[3/5] Writing Vault policies..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

vault policy write vycescore-scoring-service "$SCRIPT_DIR/policies/scoring-service.hcl"
vault policy write vycescore-feature-engineering "$SCRIPT_DIR/policies/feature-engineering.hcl"
vault policy write vycescore-admin "$SCRIPT_DIR/policies/admin.hcl"

# ---------------------------------------------------------------------------
# 4. Enable and configure Kubernetes auth
# ---------------------------------------------------------------------------
echo "[4/5] Configuring Kubernetes auth method..."

vault auth enable kubernetes 2>/dev/null || \
  echo "  Kubernetes auth already enabled."

# Get the K8s API info
K8S_HOST="https://kubernetes.default.svc"
K8S_CA_CERT=$(kubectl get cm kube-root-ca.crt -n default -o jsonpath='{.data.ca\.crt}')
REVIEWER_JWT=$(kubectl get secret \
  $(kubectl get serviceaccount vault -n vault -o jsonpath='{.secrets[0].name}') \
  -n vault -o jsonpath='{.data.token}' | base64 -d 2>/dev/null || \
  kubectl create token vault -n vault --duration=8760h)

vault write auth/kubernetes/config \
  kubernetes_host="$K8S_HOST" \
  kubernetes_ca_cert="$K8S_CA_CERT" \
  token_reviewer_jwt="$REVIEWER_JWT" \
  disable_local_ca_jwt="true"

# ---------------------------------------------------------------------------
# 5. Create Kubernetes auth roles
# ---------------------------------------------------------------------------
echo "[5/5] Creating Kubernetes auth roles..."

vault write "auth/kubernetes/role/vycescore-scoring-service" \
  bound_service_account_names="scoring-service" \
  bound_service_account_namespaces="vycescore" \
  policies="vycescore-scoring-service" \
  ttl="1h" \
  max_ttl="4h"

vault write "auth/kubernetes/role/vycescore-feature-engineering" \
  bound_service_account_names="feature-engineering" \
  bound_service_account_namespaces="vycescore" \
  policies="vycescore-feature-engineering" \
  ttl="1h" \
  max_ttl="4h"

vault write "auth/kubernetes/role/vycescore-batch-worker" \
  bound_service_account_names="batch-worker" \
  bound_service_account_namespaces="vycescore" \
  policies="vycescore-scoring-service" \
  ttl="1h" \
  max_ttl="8h"

vault write "auth/kubernetes/role/vycescore-admin" \
  bound_service_account_names="vault-admin" \
  bound_service_account_namespaces="vycescore" \
  policies="vycescore-admin" \
  ttl="30m" \
  max_ttl="2h"

echo ""
echo "=== Vault setup complete for '$ENV' ==="
echo "Secret paths:"
echo "  secret/vycescore/$ENV/db"
echo "  secret/vycescore/$ENV/redis"
echo "  secret/vycescore/$ENV/api-keys"
echo "  secret/vycescore/$ENV/kafka"
echo "  secret/vycescore/$ENV/compliance/*"
echo "  secret/vycescore/$ENV/model-config"
