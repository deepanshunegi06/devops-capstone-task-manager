output "instances" {
  description = "name / public_ip / private_ip of each instance (used for the Ansible inventory)"
  value = [for i in aws_instance.this : {
    name       = i.tags["Name"]
    public_ip  = i.public_ip
    private_ip = i.private_ip
  }]
}

output "public_ips" {
  description = "Public IPs"
  value       = aws_instance.this[*].public_ip
}

output "ids" {
  description = "Instance IDs"
  value       = aws_instance.this[*].id
}
