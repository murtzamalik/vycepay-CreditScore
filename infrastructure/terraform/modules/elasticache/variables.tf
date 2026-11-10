variable "environment" {
  description = "Environment name (dev, staging, production)"
  type        = string

  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Environment must be one of: dev, staging, production."
  }
}

variable "vpc_id" {
  description = "VPC ID for security groups"
  type        = string
}

variable "elasticache_subnet_group_name" {
  description = "Name of the ElastiCache subnet group"
  type        = string
}

variable "eks_security_group_id" {
  description = "Security group ID of the EKS cluster"
  type        = string
}

variable "redis_node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.t3.medium"
}

variable "redis_num_cache_clusters" {
  description = "Number of cache clusters (nodes). Use 2+ for multi-AZ failover."
  type        = number
  default     = 2

  validation {
    condition     = var.redis_num_cache_clusters >= 1 && var.redis_num_cache_clusters <= 6
    error_message = "Cache cluster count must be between 1 and 6."
  }
}

variable "redis_auth_token" {
  description = "Auth token (password) for Redis. Must be 16+ characters."
  type        = string
  sensitive   = true
}

variable "snapshot_retention_limit" {
  description = "Number of days to retain automatic snapshots"
  type        = number
  default     = 7
}

variable "sns_topic_arn" {
  description = "SNS topic ARN for ElastiCache event notifications"
  type        = string
  default     = ""
}
