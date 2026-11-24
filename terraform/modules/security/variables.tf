variable "name" {
  description = "Name prefix"
  type        = string
}

variable "vpc_id" {
  description = "VPC to create the security groups in"
  type        = string
}

variable "vpc_cidr" {
  description = "VPC CIDR (trusted for node-to-node traffic)"
  type        = string
}

variable "admin_cidr" {
  description = "CIDR allowed to reach admin ports"
  type        = string
}

variable "github_hook_cidrs" {
  description = "GitHub webhook source ranges (https://api.github.com/meta -> hooks)"
  type        = list(string)
  default     = ["192.30.252.0/22", "185.199.108.0/22", "140.82.112.0/20", "143.55.64.0/20"]
}
