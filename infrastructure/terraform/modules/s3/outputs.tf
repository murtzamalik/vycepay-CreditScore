output "bucket_arns" {
  description = "Map of bucket name to ARN"
  value       = { for k, b in aws_s3_bucket.main : k => b.arn }
}

output "bucket_ids" {
  description = "Map of bucket name to bucket ID"
  value       = { for k, b in aws_s3_bucket.main : k => b.id }
}

output "data_lake_bucket_arn" {
  description = "ARN of the data lake bucket"
  value       = aws_s3_bucket.main["data-lake"].arn
}

output "data_lake_bucket_id" {
  description = "ID of the data lake bucket"
  value       = aws_s3_bucket.main["data-lake"].id
}

output "model_artifacts_bucket_arn" {
  description = "ARN of the model artifacts bucket"
  value       = aws_s3_bucket.main["model-artifacts"].arn
}

output "model_artifacts_bucket_id" {
  description = "ID of the model artifacts bucket"
  value       = aws_s3_bucket.main["model-artifacts"].id
}

output "batch_results_bucket_arn" {
  description = "ARN of the batch results bucket"
  value       = aws_s3_bucket.main["batch-results"].arn
}

output "audit_logs_bucket_arn" {
  description = "ARN of the audit logs bucket"
  value       = aws_s3_bucket.main["audit-logs"].arn
}

output "kms_key_arn" {
  description = "KMS key ARN used for S3 encryption"
  value       = aws_kms_key.s3.arn
}
