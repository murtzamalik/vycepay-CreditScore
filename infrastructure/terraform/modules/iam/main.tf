###############################################################################
# VyceScore — IAM Module
# IAM roles and policies for EKS pods via IRSA
###############################################################################

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  oidc_provider_id = replace(var.oidc_provider_url, "https://", "")
}

# ---------------------------------------------------------------------------
# Scoring Service IRSA Role
# Access: S3 model artifacts (read), Secrets Manager, SQS
# ---------------------------------------------------------------------------
resource "aws_iam_role" "scoring_service" {
  name = "${var.environment}-vycescore-scoring-service"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRoleWithWebIdentity"
      Effect = "Allow"
      Principal = {
        Federated = var.oidc_provider_arn
      }
      Condition = {
        StringEquals = {
          "${local.oidc_provider_id}:sub" = "system:serviceaccount:vycescore:scoring-service"
          "${local.oidc_provider_id}:aud" = "sts.amazonaws.com"
        }
      }
    }]
  })

  tags = {
    Environment = var.environment
    Project     = "vycescore"
    Service     = "scoring-service"
  }
}

resource "aws_iam_role_policy" "scoring_service" {
  name = "${var.environment}-vycescore-scoring-service-policy"
  role = aws_iam_role.scoring_service.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3ModelRead"
        Action = [
          "s3:GetObject",
          "s3:ListBucket",
        ]
        Effect = "Allow"
        Resource = [
          var.model_artifacts_bucket_arn,
          "${var.model_artifacts_bucket_arn}/*",
        ]
      },
      {
        Sid    = "SecretsManagerRead"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret",
        ]
        Effect   = "Allow"
        Resource = "arn:aws:secretsmanager:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:secret:${var.environment}/vycescore/*"
      },
      {
        Sid    = "KMSDecrypt"
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey",
        ]
        Effect   = "Allow"
        Resource = var.s3_kms_key_arn
      },
    ]
  })
}

# ---------------------------------------------------------------------------
# Feature Engineering Service IRSA Role
# Access: S3 data lake (read/write), MSK (produce/consume)
# ---------------------------------------------------------------------------
resource "aws_iam_role" "feature_engineering" {
  name = "${var.environment}-vycescore-feature-engineering"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRoleWithWebIdentity"
      Effect = "Allow"
      Principal = {
        Federated = var.oidc_provider_arn
      }
      Condition = {
        StringEquals = {
          "${local.oidc_provider_id}:sub" = "system:serviceaccount:vycescore:feature-engineering"
          "${local.oidc_provider_id}:aud" = "sts.amazonaws.com"
        }
      }
    }]
  })

  tags = {
    Environment = var.environment
    Project     = "vycescore"
    Service     = "feature-engineering"
  }
}

resource "aws_iam_role_policy" "feature_engineering" {
  name = "${var.environment}-vycescore-feature-engineering-policy"
  role = aws_iam_role.feature_engineering.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3DataLakeReadWrite"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
        ]
        Effect = "Allow"
        Resource = [
          var.data_lake_bucket_arn,
          "${var.data_lake_bucket_arn}/*",
        ]
      },
      {
        Sid    = "MSKAccess"
        Action = [
          "kafka-cluster:Connect",
          "kafka-cluster:DescribeCluster",
          "kafka-cluster:ReadData",
          "kafka-cluster:WriteData",
          "kafka-cluster:DescribeTopic",
          "kafka-cluster:CreateTopic",
          "kafka-cluster:DescribeGroup",
          "kafka-cluster:AlterGroup",
        ]
        Effect   = "Allow"
        Resource = var.msk_cluster_arn != "" ? [var.msk_cluster_arn, "${var.msk_cluster_arn}/*"] : ["*"]
      },
      {
        Sid    = "KMSDecrypt"
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey",
        ]
        Effect   = "Allow"
        Resource = var.s3_kms_key_arn
      },
    ]
  })
}

# ---------------------------------------------------------------------------
# Batch Worker IRSA Role
# Access: S3 batch results (write), S3 data lake (read), S3 models (read)
# ---------------------------------------------------------------------------
resource "aws_iam_role" "batch_worker" {
  name = "${var.environment}-vycescore-batch-worker"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRoleWithWebIdentity"
      Effect = "Allow"
      Principal = {
        Federated = var.oidc_provider_arn
      }
      Condition = {
        StringEquals = {
          "${local.oidc_provider_id}:sub" = "system:serviceaccount:vycescore:batch-worker"
          "${local.oidc_provider_id}:aud" = "sts.amazonaws.com"
        }
      }
    }]
  })

  tags = {
    Environment = var.environment
    Project     = "vycescore"
    Service     = "batch-worker"
  }
}

resource "aws_iam_role_policy" "batch_worker" {
  name = "${var.environment}-vycescore-batch-worker-policy"
  role = aws_iam_role.batch_worker.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3BatchResultsWrite"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:ListBucket",
        ]
        Effect = "Allow"
        Resource = [
          var.batch_results_bucket_arn,
          "${var.batch_results_bucket_arn}/*",
        ]
      },
      {
        Sid    = "S3DataLakeRead"
        Action = [
          "s3:GetObject",
          "s3:ListBucket",
        ]
        Effect = "Allow"
        Resource = [
          var.data_lake_bucket_arn,
          "${var.data_lake_bucket_arn}/*",
        ]
      },
      {
        Sid    = "S3ModelsRead"
        Action = [
          "s3:GetObject",
          "s3:ListBucket",
        ]
        Effect = "Allow"
        Resource = [
          var.model_artifacts_bucket_arn,
          "${var.model_artifacts_bucket_arn}/*",
        ]
      },
      {
        Sid    = "KMSDecrypt"
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey",
        ]
        Effect   = "Allow"
        Resource = var.s3_kms_key_arn
      },
    ]
  })
}

# ---------------------------------------------------------------------------
# Feedback Service IRSA Role
# Access: S3 audit logs (write), Secrets Manager
# ---------------------------------------------------------------------------
resource "aws_iam_role" "feedback_service" {
  name = "${var.environment}-vycescore-feedback-service"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRoleWithWebIdentity"
      Effect = "Allow"
      Principal = {
        Federated = var.oidc_provider_arn
      }
      Condition = {
        StringEquals = {
          "${local.oidc_provider_id}:sub" = "system:serviceaccount:vycescore:feedback-service"
          "${local.oidc_provider_id}:aud" = "sts.amazonaws.com"
        }
      }
    }]
  })

  tags = {
    Environment = var.environment
    Project     = "vycescore"
    Service     = "feedback-service"
  }
}

resource "aws_iam_role_policy" "feedback_service" {
  name = "${var.environment}-vycescore-feedback-service-policy"
  role = aws_iam_role.feedback_service.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3AuditLogsWrite"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:ListBucket",
        ]
        Effect = "Allow"
        Resource = [
          var.audit_logs_bucket_arn,
          "${var.audit_logs_bucket_arn}/*",
        ]
      },
      {
        Sid    = "SecretsManagerRead"
        Action = [
          "secretsmanager:GetSecretValue",
        ]
        Effect   = "Allow"
        Resource = "arn:aws:secretsmanager:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:secret:${var.environment}/vycescore/*"
      },
    ]
  })
}

# ---------------------------------------------------------------------------
# External Secrets Operator IRSA Role
# Access: Secrets Manager (read), for injecting secrets into K8s
# ---------------------------------------------------------------------------
resource "aws_iam_role" "external_secrets" {
  name = "${var.environment}-vycescore-external-secrets"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRoleWithWebIdentity"
      Effect = "Allow"
      Principal = {
        Federated = var.oidc_provider_arn
      }
      Condition = {
        StringEquals = {
          "${local.oidc_provider_id}:sub" = "system:serviceaccount:external-secrets:external-secrets"
          "${local.oidc_provider_id}:aud" = "sts.amazonaws.com"
        }
      }
    }]
  })

  tags = {
    Environment = var.environment
    Project     = "vycescore"
    Service     = "external-secrets"
  }
}

resource "aws_iam_role_policy" "external_secrets" {
  name = "${var.environment}-vycescore-external-secrets-policy"
  role = aws_iam_role.external_secrets.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "SecretsManagerRead"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret",
          "secretsmanager:ListSecrets",
        ]
        Effect   = "Allow"
        Resource = "arn:aws:secretsmanager:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:secret:${var.environment}/vycescore/*"
      },
    ]
  })
}
