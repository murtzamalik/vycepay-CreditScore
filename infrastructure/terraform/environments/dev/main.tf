###############################################################################
# VyceScore — Dev Environment
###############################################################################

terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.40"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Environment = "dev"
      Project     = "vycescore"
      ManagedBy   = "terraform"
    }
  }
}

# ---------------------------------------------------------------------------
# Networking
# ---------------------------------------------------------------------------
module "networking" {
  source = "../../modules/networking"

  environment        = "dev"
  vpc_cidr           = var.vpc_cidr
  az_count           = 2
  single_nat_gateway = true # Cost saving for dev
}

# ---------------------------------------------------------------------------
# Kubernetes (EKS)
# ---------------------------------------------------------------------------
module "kubernetes" {
  source = "../../modules/kubernetes"

  environment            = "dev"
  cluster_name           = "dev-vycescore"
  kubernetes_version     = "1.29"
  vpc_id                 = module.networking.vpc_id
  private_subnet_ids     = module.networking.private_subnet_ids
  public_subnet_ids      = module.networking.public_subnet_ids
  endpoint_public_access = true

  app_node_instance_types = ["t3.medium"]
  app_node_capacity_type  = "SPOT"
  app_node_desired_size   = 2
  app_node_min_size       = 1
  app_node_max_size       = 4

  ml_node_instance_types = ["c5.large"]
  ml_node_capacity_type  = "SPOT"
  ml_node_desired_size   = 1
  ml_node_min_size       = 0
  ml_node_max_size       = 2
}

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
module "database" {
  source = "../../modules/database"

  environment                   = "dev"
  vpc_id                        = module.networking.vpc_id
  db_subnet_group_name          = module.networking.db_subnet_group_name
  elasticache_subnet_group_name = module.networking.elasticache_subnet_group_name
  eks_security_group_id         = module.kubernetes.cluster_security_group_id

  db_instance_class        = "db.t3.medium"
  db_allocated_storage     = 20
  db_max_allocated_storage = 50
  db_multi_az              = false
  db_backup_retention_days = 3
  db_master_username       = var.db_master_username
  db_master_password       = var.db_master_password

  redis_node_type          = "cache.t3.micro"
  redis_num_cache_clusters = 1
  redis_auth_token         = var.redis_auth_token
}

# ---------------------------------------------------------------------------
# S3 Buckets (data lake, model artifacts, batch results, audit logs)
# ---------------------------------------------------------------------------
module "s3" {
  source = "../../modules/s3"

  environment                    = "dev"
  enable_cross_region_replication = false
}

# ---------------------------------------------------------------------------
# MSK (Kafka)
# ---------------------------------------------------------------------------
module "msk" {
  source = "../../modules/msk"

  environment           = "dev"
  vpc_id                = module.networking.vpc_id
  private_subnet_ids    = module.networking.private_subnet_ids
  eks_security_group_id = module.kubernetes.cluster_security_group_id

  broker_count          = 2
  broker_instance_type  = "kafka.t3.small"
  broker_ebs_volume_size = 20
}

# ---------------------------------------------------------------------------
# IAM (IRSA roles for EKS pods)
# ---------------------------------------------------------------------------
module "iam" {
  source = "../../modules/iam"

  environment               = "dev"
  oidc_provider_arn         = module.kubernetes.oidc_provider_arn
  oidc_provider_url         = module.kubernetes.oidc_provider_url
  model_artifacts_bucket_arn = module.s3.model_artifacts_bucket_arn
  data_lake_bucket_arn      = module.s3.data_lake_bucket_arn
  batch_results_bucket_arn  = module.s3.batch_results_bucket_arn
  audit_logs_bucket_arn     = module.s3.audit_logs_bucket_arn
  s3_kms_key_arn            = module.s3.kms_key_arn
  msk_cluster_arn           = module.msk.cluster_arn
}

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------
output "vpc_id" {
  value = module.networking.vpc_id
}

output "eks_cluster_endpoint" {
  value = module.kubernetes.cluster_endpoint
}

output "db_endpoint" {
  value     = module.database.db_endpoint
  sensitive = true
}

output "redis_endpoint" {
  value     = module.database.redis_endpoint
  sensitive = true
}

output "msk_bootstrap_brokers" {
  value     = module.msk.bootstrap_brokers_tls
  sensitive = true
}

output "s3_bucket_arns" {
  value = module.s3.bucket_arns
}

output "scoring_service_role_arn" {
  value = module.iam.scoring_service_role_arn
}

output "feature_engineering_role_arn" {
  value = module.iam.feature_engineering_role_arn
}
