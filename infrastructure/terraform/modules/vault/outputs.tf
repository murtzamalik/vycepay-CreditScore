output "vault_kms_key_arn" {
  description = "KMS key ARN for Vault auto-unseal"
  value       = aws_kms_key.vault.arn
}

output "vault_kms_key_id" {
  description = "KMS key ID for Vault auto-unseal"
  value       = aws_kms_key.vault.key_id
}

output "vault_iam_role_arn" {
  description = "IAM role ARN for Vault"
  value       = aws_iam_role.vault.arn
}

output "vault_namespace" {
  description = "Kubernetes namespace where Vault is deployed"
  value       = kubernetes_namespace.vault.metadata[0].name
}
