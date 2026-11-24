output "cluster_sg_id" {
  description = "Security group for Kubernetes nodes"
  value       = aws_security_group.cluster.id
}

output "ci_sg_id" {
  description = "Security group for the CI server"
  value       = aws_security_group.ci.id
}
