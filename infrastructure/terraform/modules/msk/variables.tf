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

variable "private_subnet_ids" {
  description = "Private subnet IDs for MSK broker placement"
  type        = list(string)
}

variable "eks_security_group_id" {
  description = "Security group ID of the EKS cluster for ingress rules"
  type        = string
}

variable "kafka_version" {
  description = "Apache Kafka version for MSK"
  type        = string
  default     = "3.5.1"
}

variable "broker_count" {
  description = "Number of Kafka broker nodes (must be multiple of AZ count)"
  type        = number
  default     = 3

  validation {
    condition     = var.broker_count >= 2
    error_message = "Broker count must be at least 2."
  }
}

variable "broker_instance_type" {
  description = "Instance type for MSK brokers"
  type        = string
  default     = "kafka.m5.large"
}

variable "broker_ebs_volume_size" {
  description = "EBS volume size per broker in GB"
  type        = number
  default     = 100
}

variable "log_retention_hours" {
  description = "Kafka log retention in hours"
  type        = number
  default     = 168 # 7 days
}

variable "log_retention_bytes" {
  description = "Kafka log retention in bytes per partition"
  type        = number
  default     = 1073741824 # 1 GB
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
}
