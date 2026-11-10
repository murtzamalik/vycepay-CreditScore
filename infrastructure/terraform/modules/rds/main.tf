###############################################################################
# VyceScore — RDS PostgreSQL Module
# Dedicated RDS module with enhanced backup and DR configuration.
# Extends the database module's RDS resources.
###############################################################################

data "aws_region" "current" {}

# ---------------------------------------------------------------------------
# Security Group
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

# ---------------------------------------------------------------------------
# Parameter Group — PostgreSQL 15 with TimescaleDB
# ---------------------------------------------------------------------------
resource "aws_db_parameter_group" "postgres" {
  name_prefix = "${var.environment}-vycescore-pg15-"
  family      = "postgres15"
  description = "VyceScore PostgreSQL 15 parameter group with TimescaleDB"

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
    value = "pg_stat_statements,timescaledb"
  }

  parameter {
    name  = "timescaledb.max_background_workers"
    value = "8"
    apply_method = "pending-reboot"
  }

  tags = {
    Environment = var.environment
    Project     = "vycescore"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# ---------------------------------------------------------------------------
# KMS Key for RDS encryption
# ---------------------------------------------------------------------------
resource "aws_kms_key" "rds" {
  description             = "KMS key for RDS encryption - ${var.environment}"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  tags = {
    Environment = var.environment
    Project     = "vycescore"
  }
}

resource "aws_kms_alias" "rds" {
  name          = "alias/${var.environment}-vycescore-rds"
  target_key_id = aws_kms_key.rds.key_id
}

# ---------------------------------------------------------------------------
# RDS Instance — PostgreSQL 15 multi-AZ
# ---------------------------------------------------------------------------
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

  # Backup configuration — PITR + daily snapshots
  backup_retention_period = var.db_backup_retention_days
  backup_window           = "03:00-04:00"
  maintenance_window      = "Mon:04:00-Mon:05:00"
  copy_tags_to_snapshot   = true

  # Protection
  deletion_protection       = var.environment == "production"
  skip_final_snapshot       = var.environment != "production"
  final_snapshot_identifier = var.environment == "production" ? "${var.environment}-vycescore-final-${formatdate("YYYY-MM-DD", timestamp())}" : null

  # Monitoring
  performance_insights_enabled    = true
  performance_insights_kms_key_id = aws_kms_key.rds.arn
  monitoring_interval             = var.environment == "production" ? 30 : 60
  monitoring_role_arn             = aws_iam_role.rds_monitoring.arn

  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  auto_minor_version_upgrade = true

  tags = {
    Name        = "${var.environment}-vycescore"
    Environment = var.environment
    Project     = "vycescore"
    ManagedBy   = "terraform"
    Backup      = "daily"
  }
}

# ---------------------------------------------------------------------------
# Enhanced Monitoring IAM role
# ---------------------------------------------------------------------------
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
# Cross-Region Read Replica for DR (production only)
# ---------------------------------------------------------------------------
resource "aws_db_instance" "read_replica" {
  count = var.enable_cross_region_replica ? 1 : 0

  identifier          = "${var.environment}-vycescore-replica"
  replicate_source_db = aws_db_instance.main.arn
  instance_class      = var.replica_instance_class
  storage_encrypted   = true

  multi_az                = false
  auto_minor_version_upgrade = true

  monitoring_interval = 60
  monitoring_role_arn = aws_iam_role.rds_monitoring.arn

  performance_insights_enabled = true

  tags = {
    Name        = "${var.environment}-vycescore-replica"
    Environment = var.environment
    Project     = "vycescore"
    Purpose     = "disaster-recovery"
  }
}

# ---------------------------------------------------------------------------
# Backup Verification Lambda (placeholder)
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_event_rule" "backup_verification" {
  count = var.environment == "production" ? 1 : 0

  name                = "${var.environment}-vycescore-backup-verify"
  description         = "Trigger daily backup verification"
  schedule_expression = "cron(0 6 * * ? *)" # 06:00 UTC daily (after backup window)

  tags = {
    Environment = var.environment
    Project     = "vycescore"
  }
}
