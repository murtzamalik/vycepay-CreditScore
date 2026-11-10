# Passthrough variables — see ../kubernetes/variables.tf for descriptions

variable "environment" {
  type = string
}

variable "cluster_name" {
  type = string
}

variable "kubernetes_version" {
  type    = string
  default = "1.29"
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "public_subnet_ids" {
  type = list(string)
}

variable "endpoint_public_access" {
  type    = bool
  default = true
}

variable "app_node_instance_types" {
  type    = list(string)
  default = ["t3.large"]
}

variable "app_node_capacity_type" {
  type    = string
  default = "ON_DEMAND"
}

variable "app_node_desired_size" {
  type    = number
  default = 2
}

variable "app_node_min_size" {
  type    = number
  default = 1
}

variable "app_node_max_size" {
  type    = number
  default = 5
}

variable "ml_node_instance_types" {
  type    = list(string)
  default = ["c5.xlarge"]
}

variable "ml_node_capacity_type" {
  type    = string
  default = "ON_DEMAND"
}

variable "ml_node_desired_size" {
  type    = number
  default = 1
}

variable "ml_node_min_size" {
  type    = number
  default = 1
}

variable "ml_node_max_size" {
  type    = number
  default = 3
}
