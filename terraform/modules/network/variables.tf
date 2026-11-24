variable "name" {
  description = "Name prefix"
  type        = string
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
}

variable "public_subnet_cidrs" {
  description = "Public subnet CIDRs"
  type        = list(string)
}

variable "azs" {
  description = "Availability zones, same length as public_subnet_cidrs"
  type        = list(string)
}
