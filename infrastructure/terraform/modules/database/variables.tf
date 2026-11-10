variable "environment" {
  description = "Environment name (dev, staging, production)"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID for security groups"
  type        = string
}

variable "db_subnet_group_name" {
  description = "Name of the DB subnet group"
  type        = string
}

variable "elasticache_subnet_group_name" {
  description = "Name of the ElastiCache subnet group"
  type        = string
}

variable "eks_security_group_id" {
  description = "Security group ID of the EKS cluster for ingress rules"
  type        = string
}

# --- RDS PostgreSQL ---

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.medium"
}

variable "db_allocated_storage" {
  description = "Allocated storage in GB"
  type        = number
  default     = 20
}

variable "db_max_allocated_storage" {
  description = "Maximum allocated storage in GB for autoscaling"
  type        = number
  default     = 100
}

variable "db_master_username" {
  description = "Master username for the RDS instance"
  type        = string
  default     = "vycescore_admin"
  sensitive   = true
}

variable "db_master_password" {
  description = "Master password for the RDS instance"
  type        = string
  sensitive   = true
}

variable "db_multi_az" {
  description = "Enable Multi-AZ deployment"
  type        = bool
  default     = false
}

variable "db_backup_retention_days" {
  description = "Number of days to retain backups"
  type        = number
  default     = 7
}

# --- ElastiCache Redis ---

variable "redis_node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.t3.medium"
}

variable "redis_num_cache_clusters" {
  description = "Number of cache clusters (nodes) in the replication group"
  type        = number
  default     = 2
}

variable "redis_auth_token" {
  description = "Auth token (password) for Redis"
  type        = string
  sensitive   = true
}
