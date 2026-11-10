variable "environment" {
  description = "Environment name (dev, staging, production)"
  type        = string

  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Environment must be one of: dev, staging, production."
  }
}

variable "oidc_provider_arn" {
  description = "ARN of the EKS OIDC provider for IRSA"
  type        = string
}

variable "oidc_provider_url" {
  description = "URL of the EKS OIDC provider"
  type        = string
}

variable "model_artifacts_bucket_arn" {
  description = "ARN of the S3 model artifacts bucket"
  type        = string
}

variable "data_lake_bucket_arn" {
  description = "ARN of the S3 data lake bucket"
  type        = string
}

variable "batch_results_bucket_arn" {
  description = "ARN of the S3 batch results bucket"
  type        = string
}

variable "audit_logs_bucket_arn" {
  description = "ARN of the S3 audit logs bucket"
  type        = string
}

variable "s3_kms_key_arn" {
  description = "ARN of the KMS key used for S3 encryption"
  type        = string
}

variable "msk_cluster_arn" {
  description = "ARN of the MSK cluster"
  type        = string
  default     = ""
}
