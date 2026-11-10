###############################################################################
# VyceScore — Database Module
# RDS PostgreSQL 15, ElastiCache Redis cluster
###############################################################################

data "aws_region" "current" {}

# ---------------------------------------------------------------------------
# Security Groups
# ---------------------------------------------------------------------------
resource "aws_security_group" "rds" {
  name_prefix = "${var.environment}-vycescore-rds-"
  description = "Security group for VyceScore RDS PostgreSQL"
  vpc_id      = var.vpc_id

  tags = {
    Name        = "${var.environment}-vycescore-rds-sg"
    Environment = var.environment
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group_rule" "rds_ingress" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  source_security_group_id = var.eks_security_group_id
  security_group_id        = aws_security_group.rds.id
  description              = "PostgreSQL access from EKS cluster"
}

resource "aws_security_group" "redis" {
  name_prefix = "${var.environment}-vycescore-redis-"
  description = "Security group for VyceScore ElastiCache Redis"
  vpc_id      = var.vpc_id

  tags = {
    Name        = "${var.environment}-vycescore-redis-sg"
    Environment = var.environment
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group_rule" "redis_ingress" {
  type                     = "ingress"
  from_port                = 6379
  to_port                  = 6379
  protocol                 = "tcp"
  source_security_group_id = var.eks_security_group_id
  security_group_id        = aws_security_group.redis.id
  description              = "Redis access from EKS cluster"
}

# ---------------------------------------------------------------------------
# RDS PostgreSQL
# ---------------------------------------------------------------------------
resource "aws_db_parameter_group" "postgres" {
  name_prefix = "${var.environment}-vycescore-pg15-"
  family      = "postgres15"
  description = "VyceScore PostgreSQL 15 parameter group"

  parameter {
    name  = "log_connections"
    value = "1"
  }

  parameter {
    name  = "log_disconnections"
    value = "1"
  }

  parameter {
    name  = "log_statement"
    value = "ddl"
  }

  parameter {
    name  = "shared_preload_libraries"
    value = "pg_stat_statements"
  }

  tags = {
    Environment = var.environment
    Project     = "vycescore"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_kms_key" "rds" {
  description             = "KMS key for RDS encryption - ${var.environment}"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  tags = {
    Environment = var.environment
    Project     = "vycescore"
  }
}

resource "aws_db_instance" "main" {
  identifier = "${var.environment}-vycescore"

  engine               = "postgres"
  engine_version       = "15.7"
  instance_class       = var.db_instance_class
  allocated_storage    = var.db_allocated_storage
  max_allocated_storage = var.db_max_allocated_storage
  storage_type         = "gp3"
  storage_encrypted    = true
  kms_key_id           = aws_kms_key.rds.arn

  db_name  = "vycescore"
  username = var.db_master_username
  password = var.db_master_password

  multi_az               = var.db_multi_az
  db_subnet_group_name   = var.db_subnet_group_name
  vpc_security_group_ids = [aws_security_group.rds.id]
  parameter_group_name   = aws_db_parameter_group.postgres.name

  backup_retention_period = var.db_backup_retention_days
  backup_window           = "03:00-04:00"
  maintenance_window      = "Mon:04:00-Mon:05:00"

  deletion_protection       = var.environment == "production" ? true : false
  skip_final_snapshot       = var.environment == "production" ? false : true
  final_snapshot_identifier = var.environment == "production" ? "${var.environment}-vycescore-final" : null
  copy_tags_to_snapshot     = true

  performance_insights_enabled    = true
  performance_insights_kms_key_id = aws_kms_key.rds.arn
  monitoring_interval             = 60
  monitoring_role_arn             = aws_iam_role.rds_monitoring.arn

  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  auto_minor_version_upgrade = true

  tags = {
    Name        = "${var.environment}-vycescore"
    Environment = var.environment
    Project     = "vycescore"
    ManagedBy   = "terraform"
  }
}

# Enhanced Monitoring IAM role
resource "aws_iam_role" "rds_monitoring" {
  name = "${var.environment}-vycescore-rds-monitoring"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "monitoring.rds.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "rds_monitoring" {
  role       = aws_iam_role.rds_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

# ---------------------------------------------------------------------------
# ElastiCache Redis
# ---------------------------------------------------------------------------
resource "aws_elasticache_parameter_group" "redis" {
  name_prefix = "${var.environment}-vycescore-redis7-"
  family      = "redis7"
  description = "VyceScore Redis 7 parameter group"

  parameter {
    name  = "maxmemory-policy"
    value = "allkeys-lru"
  }

  parameter {
    name  = "notify-keyspace-events"
    value = "Ex"
  }

  tags = {
    Environment = var.environment
    Project     = "vycescore"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id = "${var.environment}-vycescore"
  description          = "VyceScore Redis cluster for score caching (24h TTL)"

  engine               = "redis"
  engine_version       = "7.1"
  node_type            = var.redis_node_type
  num_cache_clusters   = var.redis_num_cache_clusters
  port                 = 6379
  parameter_group_name = aws_elasticache_parameter_group.redis.name
  subnet_group_name    = var.elasticache_subnet_group_name
  security_group_ids   = [aws_security_group.redis.id]

  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token                 = var.redis_auth_token

  automatic_failover_enabled = var.redis_num_cache_clusters > 1 ? true : false
  multi_az_enabled           = var.redis_num_cache_clusters > 1 ? true : false

  snapshot_retention_limit = var.environment == "production" ? 7 : 1
  snapshot_window          = "02:00-03:00"
  maintenance_window       = "Mon:03:00-Mon:04:00"

  auto_minor_version_upgrade = true

  tags = {
    Name        = "${var.environment}-vycescore-redis"
    Environment = var.environment
    Project     = "vycescore"
    ManagedBy   = "terraform"
  }
}
