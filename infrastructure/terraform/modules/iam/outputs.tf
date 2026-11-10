output "scoring_service_role_arn" {
  description = "IAM role ARN for the scoring service (IRSA)"
  value       = aws_iam_role.scoring_service.arn
}

output "feature_engineering_role_arn" {
  description = "IAM role ARN for the feature engineering service (IRSA)"
  value       = aws_iam_role.feature_engineering.arn
}

output "batch_worker_role_arn" {
  description = "IAM role ARN for the batch worker (IRSA)"
  value       = aws_iam_role.batch_worker.arn
}

output "feedback_service_role_arn" {
  description = "IAM role ARN for the feedback service (IRSA)"
  value       = aws_iam_role.feedback_service.arn
}

output "external_secrets_role_arn" {
  description = "IAM role ARN for the External Secrets Operator (IRSA)"
  value       = aws_iam_role.external_secrets.arn
}
