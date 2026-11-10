# VyceScore Feature Engineering Service — Vault Policy
# Grants read access to database credentials and Kafka config.

# Database credentials (read-only)
path "secret/data/vycescore/{{identity.entity.aliases.auth_kubernetes_*.metadata.service_account_namespace}}/db" {
  capabilities = ["read"]
}

# Kafka/MSK credentials (read-only)
path "secret/data/vycescore/{{identity.entity.aliases.auth_kubernetes_*.metadata.service_account_namespace}}/kafka" {
  capabilities = ["read"]
}

# Redis credentials (read-only)
path "secret/data/vycescore/{{identity.entity.aliases.auth_kubernetes_*.metadata.service_account_namespace}}/redis" {
  capabilities = ["read"]
}

# S3 configuration (read-only)
path "secret/data/vycescore/{{identity.entity.aliases.auth_kubernetes_*.metadata.service_account_namespace}}/s3" {
  capabilities = ["read"]
}
