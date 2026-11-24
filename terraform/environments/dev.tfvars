# terraform apply -var-file=environments/dev.tfvars -var="admin_cidr=$(curl -s ifconfig.me)/32"
environment          = "dev"
aws_region           = "ap-south-1"
worker_count         = 1
master_instance_type = "t3.medium"
worker_instance_type = "t3.medium"
