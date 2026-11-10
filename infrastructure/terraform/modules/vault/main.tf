###############################################################################
# VyceScore — HashiCorp Vault Module
# Vault server on EKS, Kubernetes auth, secret engines, policies
###############################################################################

# ---------------------------------------------------------------------------
# Vault Namespace (dedicated K8s namespace)
# ---------------------------------------------------------------------------
resource "kubernetes_namespace" "vault" {
  metadata {
    name = "vault"

    labels = {
      "app.kubernetes.io/name"    = "vault"
      "app.kubernetes.io/part-of" = "vycescore-platform"
      environment                 = var.environment
    }
  }
}

# ---------------------------------------------------------------------------
# Vault Helm Release
# ---------------------------------------------------------------------------
resource "helm_release" "vault" {
  name       = "vault"
  namespace  = kubernetes_namespace.vault.metadata[0].name
  repository = "https://helm.releases.hashicorp.com"
  chart      = "vault"
  version    = var.vault_helm_version

  values = [
    yamlencode({
      global = {
        enabled    = true
        tlsDisable = false
      }

      server = {
        enabled = true

        resources = {
          requests = {
            memory = var.environment == "production" ? "512Mi" : "256Mi"
            cpu    = var.environment == "production" ? "500m" : "250m"
          }
          limits = {
            memory = var.environment == "production" ? "1Gi" : "512Mi"
            cpu    = var.environment == "production" ? "1" : "500m"
          }
        }

        ha = {
          enabled  = var.environment == "production"
          replicas = var.environment == "production" ? 3 : 1

          raft = {
            enabled   = true
            setNodeId = true

            config = <<-EOF
              ui = true

              listener "tcp" {
                tls_disable = 0
                address     = "[::]:8200"
                cluster_address = "[::]:8201"
                tls_cert_file = "/vault/userconfig/vault-tls/tls.crt"
                tls_key_file  = "/vault/userconfig/vault-tls/tls.key"
              }

              storage "raft" {
                path = "/vault/data"
              }

              seal "awskms" {
                region     = "${var.aws_region}"
                kms_key_id = "${var.vault_kms_key_id}"
              }

              service_registration "kubernetes" {}

              telemetry {
                prometheus_retention_time = "30s"
                disable_hostname         = true
              }
            EOF
          }
        }

        dataStorage = {
          enabled      = true
          size         = var.environment == "production" ? "10Gi" : "5Gi"
          storageClass = "gp3"
        }

        auditStorage = {
          enabled      = true
          size         = "5Gi"
          storageClass = "gp3"
        }

        ingress = {
          enabled = false # Access via port-forward or internal LB only
        }

        serviceAccount = {
          create = true
          name   = "vault"
          annotations = {
            "eks.amazonaws.com/role-arn" = var.vault_iam_role_arn
          }
        }
      }

      injector = {
        enabled = true
        resources = {
          requests = {
            memory = "64Mi"
            cpu    = "50m"
          }
          limits = {
            memory = "128Mi"
            cpu    = "250m"
          }
        }
      }

      ui = {
        enabled = var.environment != "production"
      }
    })
  ]
}

# ---------------------------------------------------------------------------
# KMS Key for Vault Auto-Unseal
# ---------------------------------------------------------------------------
resource "aws_kms_key" "vault" {
  description             = "KMS key for Vault auto-unseal - ${var.environment}"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  tags = {
    Environment = var.environment
    Project     = "vycescore"
    Purpose     = "vault-auto-unseal"
  }
}

resource "aws_kms_alias" "vault" {
  name          = "alias/${var.environment}-vycescore-vault"
  target_key_id = aws_kms_key.vault.key_id
}

# ---------------------------------------------------------------------------
# IAM Role for Vault (auto-unseal + Secrets Manager)
# ---------------------------------------------------------------------------
resource "aws_iam_role" "vault" {
  name = "${var.environment}-vycescore-vault"

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
          "${replace(var.oidc_provider_url, "https://", "")}:sub" = "system:serviceaccount:vault:vault"
          "${replace(var.oidc_provider_url, "https://", "")}:aud" = "sts.amazonaws.com"
        }
      }
    }]
  })

  tags = {
    Environment = var.environment
    Project     = "vycescore"
  }
}

resource "aws_iam_role_policy" "vault" {
  name = "${var.environment}-vycescore-vault-policy"
  role = aws_iam_role.vault.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "VaultKMSUnseal"
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:DescribeKey",
        ]
        Effect   = "Allow"
        Resource = aws_kms_key.vault.arn
      },
      {
        Sid    = "VaultDynamoDB"
        Action = [
          "dynamodb:DescribeTable",
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan",
        ]
        Effect   = "Allow"
        Resource = "arn:aws:dynamodb:${var.aws_region}:*:table/${var.environment}-vycescore-vault-*"
      },
    ]
  })
}
