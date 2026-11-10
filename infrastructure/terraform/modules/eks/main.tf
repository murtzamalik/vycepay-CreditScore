###############################################################################
# VyceScore — EKS Module (alias)
# Wraps the kubernetes module with EKS-specific naming.
# The actual implementation lives in ../kubernetes/
# This module exists to match the Phase 13 naming convention.
###############################################################################

module "kubernetes" {
  source = "../kubernetes"

  environment            = var.environment
  cluster_name           = var.cluster_name
  kubernetes_version     = var.kubernetes_version
  vpc_id                 = var.vpc_id
  private_subnet_ids     = var.private_subnet_ids
  public_subnet_ids      = var.public_subnet_ids
  endpoint_public_access = var.endpoint_public_access

  app_node_instance_types = var.app_node_instance_types
  app_node_capacity_type  = var.app_node_capacity_type
  app_node_desired_size   = var.app_node_desired_size
  app_node_min_size       = var.app_node_min_size
  app_node_max_size       = var.app_node_max_size

  ml_node_instance_types = var.ml_node_instance_types
  ml_node_capacity_type  = var.ml_node_capacity_type
  ml_node_desired_size   = var.ml_node_desired_size
  ml_node_min_size       = var.ml_node_min_size
  ml_node_max_size       = var.ml_node_max_size
}
