###############################################################################
# VyceScore — S3 Module
# Buckets for data lake, model artifacts, batch results, and audit logs
###############################################################################

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  buckets = {
    data-lake = {
      description        = "Feature store data lake (Parquet files)"
      versioning_enabled = true
      lifecycle_rules    = true
    }
    model-artifacts = {
      description        = "ML model artifacts (XGBoost, SHAP)"
      versioning_enabled = true
      lifecycle_rules    = false
    }
    batch-results = {
      description        = "Batch scoring results and reports"
      versioning_enabled = false
      lifecycle_rules    = true
    }
    audit-logs = {
      description        = "Immutable audit trail for compliance"
      versioning_enabled = true
      lifecycle_rules    = true
    }
  }
}

# ---------------------------------------------------------------------------
# KMS Key for S3 encryption
# ---------------------------------------------------------------------------
resource "aws_kms_key" "s3" {
  description             = "KMS key for S3 bucket encryption - ${var.environment}-vycescore"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "EnableRootAccountFullAccess"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "AllowS3ServiceUsage"
        Effect = "Allow"
        Principal = {
          Service = "s3.amazonaws.com"
        }
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey"
        ]
        Resource = "*"
      }
    ]
  })

  tags = {
    Environment = var.environment
    Project     = "vycescore"
  }
}

resource "aws_kms_alias" "s3" {
  name          = "alias/${var.environment}-vycescore-s3"
  target_key_id = aws_kms_key.s3.key_id
}

# ---------------------------------------------------------------------------
# S3 Buckets
# ---------------------------------------------------------------------------
resource "aws_s3_bucket" "main" {
  for_each = local.buckets

  bucket = "${var.environment}-vycescore-${each.key}"

  tags = {
    Name        = "${var.environment}-vycescore-${each.key}"
    Description = each.value.description
    Environment = var.environment
    Project     = "vycescore"
    ManagedBy   = "terraform"
  }
}

resource "aws_s3_bucket_versioning" "main" {
  for_each = local.buckets

  bucket = aws_s3_bucket.main[each.key].id

  versioning_configuration {
    status = each.value.versioning_enabled ? "Enabled" : "Suspended"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "main" {
  for_each = local.buckets

  bucket = aws_s3_bucket.main[each.key].id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.s3.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "main" {
  for_each = local.buckets

  bucket = aws_s3_bucket.main[each.key].id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ---------------------------------------------------------------------------
# Lifecycle Rules — transition to cheaper storage tiers
# ---------------------------------------------------------------------------
resource "aws_s3_bucket_lifecycle_configuration" "main" {
  for_each = { for k, v in local.buckets : k => v if v.lifecycle_rules }

  bucket = aws_s3_bucket.main[each.key].id

  rule {
    id     = "transition-to-ia"
    status = "Enabled"

    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 365
      storage_class = "GLACIER"
    }

    # 10-year retention for compliance (Kenya DPA 2019)
    expiration {
      days = 3650
    }

    noncurrent_version_expiration {
      noncurrent_days = 90
    }
  }
}

# ---------------------------------------------------------------------------
# Audit Logs Bucket — Object Lock for immutability
# ---------------------------------------------------------------------------
resource "aws_s3_bucket_object_lock_configuration" "audit" {
  bucket = aws_s3_bucket.main["audit-logs"].id

  rule {
    default_retention {
      mode = "COMPLIANCE"
      days = 3650 # 10 years — Kenya DPA 2019
    }
  }
}

# ---------------------------------------------------------------------------
# Bucket Policies — enforce encryption in transit
# ---------------------------------------------------------------------------
resource "aws_s3_bucket_policy" "enforce_tls" {
  for_each = local.buckets

  bucket = aws_s3_bucket.main[each.key].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyUnencryptedTransport"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.main[each.key].arn,
          "${aws_s3_bucket.main[each.key].arn}/*"
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      }
    ]
  })
}

# ---------------------------------------------------------------------------
# Cross-Region Replication for DR (production only)
# ---------------------------------------------------------------------------
resource "aws_s3_bucket" "dr_replica" {
  count = var.enable_cross_region_replication ? 1 : 0

  provider = aws.dr_region
  bucket   = "${var.environment}-vycescore-dr-replica"

  tags = {
    Name        = "${var.environment}-vycescore-dr-replica"
    Environment = var.environment
    Project     = "vycescore"
    Purpose     = "disaster-recovery"
  }
}

resource "aws_iam_role" "replication" {
  count = var.enable_cross_region_replication ? 1 : 0

  name = "${var.environment}-vycescore-s3-replication"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "s3.amazonaws.com"
      }
    }]
  })

  tags = {
    Environment = var.environment
    Project     = "vycescore"
  }
}

resource "aws_iam_role_policy" "replication" {
  count = var.enable_cross_region_replication ? 1 : 0

  name = "${var.environment}-vycescore-s3-replication-policy"
  role = aws_iam_role.replication[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "s3:GetReplicationConfiguration",
          "s3:ListBucket"
        ]
        Effect   = "Allow"
        Resource = [for b in aws_s3_bucket.main : b.arn]
      },
      {
        Action = [
          "s3:GetObjectVersionForReplication",
          "s3:GetObjectVersionAcl",
          "s3:GetObjectVersionTagging"
        ]
        Effect   = "Allow"
        Resource = [for b in aws_s3_bucket.main : "${b.arn}/*"]
      },
      {
        Action = [
          "s3:ReplicateObject",
          "s3:ReplicateDelete",
          "s3:ReplicateTags"
        ]
        Effect   = "Allow"
        Resource = "${aws_s3_bucket.dr_replica[0].arn}/*"
      }
    ]
  })
}
