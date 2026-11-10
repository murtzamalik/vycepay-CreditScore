###############################################################################
# VyceScore — Amazon MSK (Managed Streaming for Apache Kafka) Module
###############################################################################

data "aws_region" "current" {}

# ---------------------------------------------------------------------------
# CloudWatch Log Group for MSK broker logs
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "msk" {
  name              = "/aws/msk/${var.environment}-vycescore"
  retention_in_days = var.log_retention_days

  tags = {
    Environment = var.environment
    Project     = "vycescore"
    ManagedBy   = "terraform"
  }
}

# ---------------------------------------------------------------------------
# KMS Key for MSK encryption
# ---------------------------------------------------------------------------
resource "aws_kms_key" "msk" {
  description             = "KMS key for MSK encryption - ${var.environment}-vycescore"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  tags = {
    Environment = var.environment
    Project     = "vycescore"
  }
}

resource "aws_kms_alias" "msk" {
  name          = "alias/${var.environment}-vycescore-msk"
  target_key_id = aws_kms_key.msk.key_id
}

# ---------------------------------------------------------------------------
# MSK Configuration
# ---------------------------------------------------------------------------
resource "aws_msk_configuration" "main" {
  name              = "${var.environment}-vycescore-msk-config"
  kafka_versions    = [var.kafka_version]
  description       = "VyceScore MSK configuration for ${var.environment}"

  server_properties = <<-PROPERTIES
    auto.create.topics.enable=true
    default.replication.factor=${var.broker_count >= 3 ? 3 : var.broker_count}
    min.insync.replicas=${var.broker_count >= 3 ? 2 : 1}
    num.io.threads=8
    num.network.threads=5
    num.partitions=6
    num.replica.fetchers=2
    replica.lag.time.max.ms=30000
    socket.receive.buffer.bytes=102400
    socket.request.max.bytes=104857600
    socket.send.buffer.bytes=102400
    unclean.leader.election.enable=false
    log.retention.hours=${var.log_retention_hours}
    log.retention.bytes=${var.log_retention_bytes}
    zookeeper.session.timeout.ms=18000
    message.max.bytes=10485760
  PROPERTIES
}

# ---------------------------------------------------------------------------
# Security Group
# ---------------------------------------------------------------------------
resource "aws_security_group" "msk" {
  name_prefix = "${var.environment}-vycescore-msk-"
  description = "Security group for VyceScore MSK cluster"
  vpc_id      = var.vpc_id

  tags = {
    Name        = "${var.environment}-vycescore-msk-sg"
    Environment = var.environment
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group_rule" "msk_ingress_plaintext" {
  type                     = "ingress"
  from_port                = 9092
  to_port                  = 9092
  protocol                 = "tcp"
  source_security_group_id = var.eks_security_group_id
  security_group_id        = aws_security_group.msk.id
  description              = "Kafka plaintext access from EKS"
}

resource "aws_security_group_rule" "msk_ingress_tls" {
  type                     = "ingress"
  from_port                = 9094
  to_port                  = 9094
  protocol                 = "tcp"
  source_security_group_id = var.eks_security_group_id
  security_group_id        = aws_security_group.msk.id
  description              = "Kafka TLS access from EKS"
}

resource "aws_security_group_rule" "msk_ingress_iam" {
  type                     = "ingress"
  from_port                = 9098
  to_port                  = 9098
  protocol                 = "tcp"
  source_security_group_id = var.eks_security_group_id
  security_group_id        = aws_security_group.msk.id
  description              = "Kafka IAM auth access from EKS"
}

resource "aws_security_group_rule" "msk_ingress_zk" {
  type                     = "ingress"
  from_port                = 2181
  to_port                  = 2181
  protocol                 = "tcp"
  source_security_group_id = var.eks_security_group_id
  security_group_id        = aws_security_group.msk.id
  description              = "Zookeeper access from EKS"
}

resource "aws_security_group_rule" "msk_egress" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.msk.id
  description       = "Allow all outbound traffic"
}

# ---------------------------------------------------------------------------
# MSK Cluster
# ---------------------------------------------------------------------------
resource "aws_msk_cluster" "main" {
  cluster_name           = "${var.environment}-vycescore"
  kafka_version          = var.kafka_version
  number_of_broker_nodes = var.broker_count

  configuration_info {
    arn      = aws_msk_configuration.main.arn
    revision = aws_msk_configuration.main.latest_revision
  }

  broker_node_group_info {
    instance_type   = var.broker_instance_type
    client_subnets  = var.private_subnet_ids
    security_groups = [aws_security_group.msk.id]

    storage_info {
      ebs_storage_info {
        volume_size = var.broker_ebs_volume_size

        provisioned_throughput {
          enabled           = var.environment == "production"
          volume_throughput  = var.environment == "production" ? 250 : null
        }
      }
    }

    connectivity_info {
      public_access {
        type = "DISABLED"
      }
    }
  }

  encryption_info {
    encryption_at_rest_kms_key_arn = aws_kms_key.msk.arn
    encryption_in_transit {
      client_broker = var.environment == "production" ? "TLS" : "TLS_PLAINTEXT"
      in_cluster    = true
    }
  }

  client_authentication {
    sasl {
      iam   = true
      scram = false
    }
  }

  logging_info {
    broker_logs {
      cloudwatch_logs {
        enabled   = true
        log_group = aws_cloudwatch_log_group.msk.name
      }
    }
  }

  open_monitoring {
    prometheus {
      jmx_exporter {
        enabled_in_broker = true
      }
      node_exporter {
        enabled_in_broker = true
      }
    }
  }

  tags = {
    Name        = "${var.environment}-vycescore-msk"
    Environment = var.environment
    Project     = "vycescore"
    ManagedBy   = "terraform"
  }
}
