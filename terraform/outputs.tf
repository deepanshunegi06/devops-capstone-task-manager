output "vpc_id" {
  description = "ID of the created VPC"
  value       = module.network.vpc_id
}

output "k8s_master_public_ip" {
  description = "Public IP of the Kubernetes control plane"
  value       = module.k8s_master.public_ips[0]
}

output "k8s_worker_public_ips" {
  description = "Public IPs of the Kubernetes workers"
  value       = module.k8s_workers.public_ips
}

output "jenkins_url" {
  description = "Jenkins UI (port 8081) - also the GitHub webhook target: <url>/github-webhook/"
  value       = "http://${module.jenkins.public_ips[0]}:8081/"
}

output "sonarqube_url" {
  description = "SonarQube UI"
  value       = "http://${module.jenkins.public_ips[0]}:9000/"
}

output "app_url" {
  description = "Application via the ingress NodePort (add taskmanager.local to /etc/hosts or use nip.io)"
  value       = "http://taskmanager.${module.k8s_master.public_ips[0]}.nip.io"
}

output "ssh_master" {
  description = "SSH command for the control plane"
  value       = "ssh -i ${local_sensitive_file.private_key.filename} ubuntu@${module.k8s_master.public_ips[0]}"
}

output "ansible_inventory_file" {
  description = "Generated inventory for the Ansible playbooks"
  value       = local_file.ansible_inventory.filename
}
