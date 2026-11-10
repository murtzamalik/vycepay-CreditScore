# VyceScore Admin — Vault Policy
# Full access to VyceScore secrets for platform operators.

# Full CRUD on all VyceScore secrets
path "secret/data/vycescore/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

path "secret/metadata/vycescore/*" {
  capabilities = ["list", "read", "delete"]
}

# Manage auth methods and policies (limited)
path "auth/kubernetes/role/vycescore-*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

path "sys/policies/acl/vycescore-*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

# Health and status
path "sys/health" {
  capabilities = ["read"]
}
