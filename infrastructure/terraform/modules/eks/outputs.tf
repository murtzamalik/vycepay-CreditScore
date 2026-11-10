output "cluster_id" {
  value = module.kubernetes.cluster_id
}

output "cluster_endpoint" {
  value = module.kubernetes.cluster_endpoint
}

output "cluster_certificate_authority_data" {
  value = module.kubernetes.cluster_certificate_authority_data
}

output "cluster_security_group_id" {
  value = module.kubernetes.cluster_security_group_id
}

output "oidc_provider_arn" {
  value = module.kubernetes.oidc_provider_arn
}

output "oidc_provider_url" {
  value = module.kubernetes.oidc_provider_url
}

output "scoring_service_role_arn" {
  value = module.kubernetes.scoring_service_role_arn
}

output "node_group_role_arn" {
  value = module.kubernetes.node_group_role_arn
}
