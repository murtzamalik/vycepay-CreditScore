variable "environment" {
  description = "Environment name (dev, staging, production)"
  type        = string

  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Environment must be one of: dev, staging, production."
  }
}

variable "enable_cross_region_replication" {
  description = "Enable cross-region replication for DR (production only)"
  type        = bool
  default     = false
}

variable "dr_region" {
  description = "DR region for cross-region replication"
  type        = string
  default     = "eu-west-1"
}
