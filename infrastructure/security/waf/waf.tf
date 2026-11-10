# VyceScore WAF Configuration — Terraform (Phase 12.8)
#
# Deploys AWS WAFv2 Web ACL with OWASP Top 10 protection.
# Attach to ALB, API Gateway, or CloudFront distribution.

resource "aws_wafv2_web_acl" "vycescore" {
  name        = "vycescore-waf"
  description = "WAF for VyceScore API — OWASP Top 10 protection"
  scope       = "REGIONAL" # Use "CLOUDFRONT" for CloudFront distributions

  default_action {
    allow {}
  }

  # ── OWASP Core Rule Set ──
  rule {
    name     = "AWSManagedRulesCommonRuleSet"
    priority = 1

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "vycescore-common-rules"
      sampled_requests_enabled   = true
    }
  }

  # ── SQL Injection ──
  rule {
    name     = "AWSManagedRulesSQLiRuleSet"
    priority = 2

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesSQLiRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "vycescore-sqli-rules"
      sampled_requests_enabled   = true
    }
  }

  # ── Known Bad Inputs (Log4j, SSRF, etc.) ──
  rule {
    name     = "AWSManagedRulesKnownBadInputsRuleSet"
    priority = 3

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesKnownBadInputsRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "vycescore-bad-inputs"
      sampled_requests_enabled   = true
    }
  }

  # ── IP Reputation ──
  rule {
    name     = "AWSManagedRulesAmazonIpReputationList"
    priority = 4

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesAmazonIpReputationList"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "vycescore-ip-reputation"
      sampled_requests_enabled   = true
    }
  }

  # ── Rate Limiting (general) ──
  rule {
    name     = "RateLimitGeneral"
    priority = 5

    action {
      block {
        custom_response {
          response_code = 429
          custom_response_body_key = "waf_rate_limited"
        }
      }
    }

    statement {
      rate_based_statement {
        limit              = 2000
        aggregate_key_type = "IP"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "vycescore-rate-limit"
      sampled_requests_enabled   = true
    }
  }

  # ── Auth endpoint brute-force protection ──
  rule {
    name     = "RateLimitAuth"
    priority = 6

    action {
      block {
        custom_response {
          response_code = 429
          custom_response_body_key = "waf_rate_limited"
        }
      }
    }

    statement {
      rate_based_statement {
        limit              = 20
        aggregate_key_type = "IP"

        scope_down_statement {
          byte_match_statement {
            search_string         = "/v1/auth"
            positional_constraint = "STARTS_WITH"

            field_to_match {
              uri_path {}
            }

            text_transformation {
              priority = 0
              type     = "LOWERCASE"
            }
          }
        }
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "vycescore-auth-rate-limit"
      sampled_requests_enabled   = true
    }
  }

  custom_response_body {
    key          = "waf_rate_limited"
    content      = "{\"error\":{\"code\":\"RATE_LIMITED\",\"message\":\"Too many requests\",\"details\":{}}}"
    content_type = "APPLICATION_JSON"
  }

  custom_response_body {
    key          = "waf_blocked"
    content      = "{\"error\":{\"code\":\"WAF_BLOCKED\",\"message\":\"Request blocked by security policy\",\"details\":{}}}"
    content_type = "APPLICATION_JSON"
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "vycescore-waf"
    sampled_requests_enabled   = true
  }

  tags = {
    Project     = "VyceScore"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# ── WAF Logging ──
resource "aws_wafv2_web_acl_logging_configuration" "vycescore" {
  log_destination_configs = [aws_s3_bucket.waf_logs.arn]
  resource_arn            = aws_wafv2_web_acl.vycescore.arn

  redacted_fields {
    single_header {
      name = "authorization"
    }
  }

  redacted_fields {
    single_header {
      name = "x-api-key"
    }
  }
}

# ── Associate with ALB ──
resource "aws_wafv2_web_acl_association" "alb" {
  resource_arn = var.alb_arn
  web_acl_arn  = aws_wafv2_web_acl.vycescore.arn
}

variable "environment" {
  description = "Deployment environment (dev/staging/production)"
  type        = string
  default     = "production"
}

variable "alb_arn" {
  description = "ARN of the Application Load Balancer to protect"
  type        = string
}
