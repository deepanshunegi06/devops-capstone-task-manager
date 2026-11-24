variable "name" {
  description = "Instance name (suffixed with an index when instance_count > 1)"
  type        = string
}

variable "instance_count" {
  description = "How many instances to create"
  type        = number
  default     = 1
}

variable "role" {
  description = "Ansible group / role tag for these instances"
  type        = string
}

variable "ami_id" {
  description = "AMI to launch"
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
}

variable "subnet_ids" {
  description = "Subnets to spread the instances across"
  type        = list(string)
}

variable "security_group_ids" {
  description = "Security groups to attach"
  type        = list(string)
}

variable "key_name" {
  description = "EC2 key pair name"
  type        = string
}

variable "root_volume_size" {
  description = "Root volume size in GiB"
  type        = number
  default     = 30
}
