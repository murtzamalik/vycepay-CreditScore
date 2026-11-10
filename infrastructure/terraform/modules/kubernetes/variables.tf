variable "environment" {
  description = "Environment name (dev, staging, production)"
  type        = string
}

variable "cluster_name" {
  description = "Name of the EKS cluster"
  type        = string
}

variable "kubernetes_version" {
  description = "Kubernetes version for EKS"
  type        = string
  default     = "1.29"
}

variable "vpc_id" {
  description = "VPC ID where the cluster will be deployed"
  type        = string
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs for worker nodes"
  type        = list(string)
}

variable "public_subnet_ids" {
  description = "List of public subnet IDs for load balancers"
  type        = list(string)
}

variable "endpoint_public_access" {
  description = "Whether the EKS API server endpoint is publicly accessible"
  type        = bool
  default     = true
}

# --- Application Node Group ---

variable "app_node_instance_types" {
  description = "Instance types for the application node group"
  type        = list(string)
  default     = ["t3.large"]
}

variable "app_node_capacity_type" {
  description = "Capacity type for app nodes (ON_DEMAND or SPOT)"
  type        = string
  default     = "ON_DEMAND"
}

variable "app_node_desired_size" {
  description = "Desired number of application nodes"
  type        = number
  default     = 2
}

variable "app_node_min_size" {
  description = "Minimum number of application nodes"
  type        = number
  default     = 1
}

variable "app_node_max_size" {
  description = "Maximum number of application nodes"
  type        = number
  default     = 5
}

# --- ML Inference Node Group ---

variable "ml_node_instance_types" {
  description = "Instance types for the ML inference node group"
  type        = list(string)
  default     = ["c5.xlarge"]
}

variable "ml_node_capacity_type" {
  description = "Capacity type for ML nodes (ON_DEMAND or SPOT)"
  type        = string
  default     = "ON_DEMAND"
}

variable "ml_node_desired_size" {
  description = "Desired number of ML inference nodes"
  type        = number
  default     = 1
}

variable "ml_node_min_size" {
  description = "Minimum number of ML inference nodes"
  type        = number
  default     = 1
}

variable "ml_node_max_size" {
  description = "Maximum number of ML inference nodes"
  type        = number
  default     = 3
}
