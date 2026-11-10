variable "environment" {
  description = "Environment name (dev, staging, production)"
  type        = string

  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Environment must be one of: dev, staging, production."
  }
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "af-south-1"
}

variable "vault_helm_version" {
  description = "Vault Helm chart version"
  type        = string
  default     = "0.27.0"
}

variable "vault_kms_key_id" {
  description = "KMS key ID for Vault auto-unseal (set after creation)"
  type        = string
  default     = ""
}

variable "vault_iam_role_arn" {
  description = "IAM role ARN for Vault service account"
  type        = string
  default     = ""
}

variable "oidc_provider_arn" {
  description = "ARN of the EKS OIDC provider"
  type        = string
}

variable "oidc_provider_url" {
  description = "URL of the EKS OIDC provider"
  type        = string
}
