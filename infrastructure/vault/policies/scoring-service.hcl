# VyceScore Scoring Service — Vault Policy
# Grants read access to database credentials, Redis, API keys, and model config.

# Database credentials (read-only)
path "secret/data/vycescore/{{identity.entity.aliases.auth_kubernetes_*.metadata.service_account_namespace}}/db" {
  capabilities = ["read"]
}

# Redis credentials (read-only)
path "secret/data/vycescore/{{identity.entity.aliases.auth_kubernetes_*.metadata.service_account_namespace}}/redis" {
  capabilities = ["read"]
}

# API keys (read-only)
path "secret/data/vycescore/{{identity.entity.aliases.auth_kubernetes_*.metadata.service_account_namespace}}/api-keys" {
  capabilities = ["read"]
}

# Model configuration (read-only)
path "secret/data/vycescore/{{identity.entity.aliases.auth_kubernetes_*.metadata.service_account_namespace}}/model-config" {
  capabilities = ["read"]
}

# Compliance partner credentials (read-only)
path "secret/data/vycescore/{{identity.entity.aliases.auth_kubernetes_*.metadata.service_account_namespace}}/compliance/*" {
  capabilities = ["read"]
}

# Deny access to write or delete any secrets
path "secret/data/vycescore/*" {
  capabilities = ["deny"]
  allowed_parameters = {}
}
