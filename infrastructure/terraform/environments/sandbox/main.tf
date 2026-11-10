###############################################################################
# VyceScore — Sandbox Environment
# Isolated environment for partner integration testing.
# Shares the dev EKS cluster but uses a separate namespace and
# logically isolated database/cache.
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
      Environment = "sandbox"
      Project     = "vycescore"
      ManagedBy   = "terraform"
    }
  }
}

# ---------------------------------------------------------------------------
# Data sources — reference the dev VPC and EKS cluster
# ---------------------------------------------------------------------------
data "terraform_remote_state" "dev" {
  backend = "s3"
  config = {
    bucket = "vycescore-terraform-state"
    key    = "dev/terraform.tfstate"
    region = "af-south-1"
  }
}

# ---------------------------------------------------------------------------
# Sandbox Database (smaller, single-AZ)
# ---------------------------------------------------------------------------
module "database" {
  source = "../../modules/database"

  environment                   = "sandbox"
  vpc_id                        = data.terraform_remote_state.dev.outputs.vpc_id
  db_subnet_group_name          = "dev-vycescore-db-subnet" # reuse dev subnets
  elasticache_subnet_group_name = "dev-vycescore-cache-subnet"
  eks_security_group_id         = data.terraform_remote_state.dev.outputs.eks_cluster_endpoint != "" ? data.terraform_remote_state.dev.outputs.vpc_id : ""

  db_instance_class        = "db.t3.micro"
  db_allocated_storage     = 10
  db_max_allocated_storage = 20
  db_multi_az              = false
  db_backup_retention_days = 1
  db_master_username       = var.db_master_username
  db_master_password       = var.db_master_password

  redis_node_type          = "cache.t3.micro"
  redis_num_cache_clusters = 1
  redis_auth_token         = var.redis_auth_token
}

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------
output "db_endpoint" {
  value     = module.database.db_endpoint
  sensitive = true
}

output "redis_endpoint" {
  value     = module.database.redis_endpoint
  sensitive = true
}
