###############################################################################
# VyceScore — ElastiCache Redis Module
# Redis 7 cluster with multi-AZ, encryption, backups, and failover
###############################################################################

# ---------------------------------------------------------------------------
# Security Group
# ---------------------------------------------------------------------------
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
# Parameter Group — Redis 7 with RDB + AOF persistence
# ---------------------------------------------------------------------------
resource "aws_elasticache_parameter_group" "redis" {
  name_prefix = "${var.environment}-vycescore-redis7-"
  family      = "redis7"
  description = "VyceScore Redis 7 with RDB+AOF persistence"

  parameter {
    name  = "maxmemory-policy"
    value = "allkeys-lru"
  }

  parameter {
    name  = "notify-keyspace-events"
    value = "Ex"
  }

  # AOF persistence — append-only file for durability
  parameter {
    name  = "appendonly"
    value = "yes"
  }

  parameter {
    name  = "appendfsync"
    value = "everysec"
  }

  # RDB persistence — periodic snapshots
  parameter {
    name  = "save"
    value = "900 1 300 10 60 10000"
  }

  # Slow log for debugging
  parameter {
    name  = "slowlog-log-slower-than"
    value = "10000"
  }

  parameter {
    name  = "slowlog-max-len"
    value = "128"
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
# ElastiCache Replication Group — multi-AZ with auto-failover
# ---------------------------------------------------------------------------
resource "aws_elasticache_replication_group" "redis" {
  replication_group_id = "${var.environment}-vycescore"
  description          = "VyceScore Redis cluster — score cache (24h TTL), ${var.environment}"

  engine               = "redis"
  engine_version       = "7.1"
  node_type            = var.redis_node_type
  num_cache_clusters   = var.redis_num_cache_clusters
  port                 = 6379
  parameter_group_name = aws_elasticache_parameter_group.redis.name
  subnet_group_name    = var.elasticache_subnet_group_name
  security_group_ids   = [aws_security_group.redis.id]

  # Encryption
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token                 = var.redis_auth_token

  # HA: auto-failover + multi-AZ when > 1 node
  automatic_failover_enabled = var.redis_num_cache_clusters > 1
  multi_az_enabled           = var.redis_num_cache_clusters > 1

  # Snapshots / Backups
  snapshot_retention_limit = var.snapshot_retention_limit
  snapshot_window          = "02:00-03:00"
  maintenance_window       = "Mon:03:00-Mon:04:00"

  auto_minor_version_upgrade = true

  # Notifications
  notification_topic_arn = var.sns_topic_arn != "" ? var.sns_topic_arn : null

  tags = {
    Name        = "${var.environment}-vycescore-redis"
    Environment = var.environment
    Project     = "vycescore"
    ManagedBy   = "terraform"
  }
}
