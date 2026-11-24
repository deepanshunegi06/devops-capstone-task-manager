variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "ap-south-1"
}

variable "project_name" {
  description = "Prefix used for every resource name"
  type        = string
  default     = "taskmanager"
}

variable "environment" {
  description = "Environment name (dev, prod...)"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod."
  }
}

variable "vpc_cidr" {
  description = "CIDR block of the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "One public subnet per availability zone"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "admin_cidr" {
  description = "Your public IP in CIDR form - the only source allowed to SSH / reach Jenkins / the K8s API"
  type        = string

  validation {
    condition     = can(cidrhost(var.admin_cidr, 0))
    error_message = "admin_cidr must be a valid CIDR, e.g. 203.0.113.7/32."
  }
}

variable "worker_count" {
  description = "Number of Kubernetes worker nodes"
  type        = number
  default     = 2
}

variable "master_instance_type" {
  description = "EC2 type for the Kubernetes control plane (kubeadm needs >= 2 vCPU, 2 GB)"
  type        = string
  default     = "t3.medium"
}

variable "worker_instance_type" {
  description = "EC2 type for Kubernetes workers"
  type        = string
  default     = "t3.large"
}

variable "jenkins_instance_type" {
  description = "EC2 type for the Jenkins + SonarQube server"
  type        = string
  default     = "t3.large"
}

variable "root_volume_size" {
  description = "Root EBS volume size (GiB)"
  type        = number
  default     = 30
}
