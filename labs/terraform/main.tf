terraform {
  required_providers {
    docker = { source = "kreuzwerker/docker", version = "3.0.2" }
  }
}
variable "docker_host" { type = string }
variable "replicas" {
  type = number
  default = 2
  validation {
    condition = var.replicas >= 1 && var.replicas <= 3
    error_message = "Use between one and three isolated lab replicas."
  }
}
provider "docker" { host = var.docker_host }
resource "docker_image" "app" {
  name = "deepanshunegi06/taskmanager:2.0.0"
  keep_locally = true
}
resource "docker_container" "replica" {
  count = var.replicas
  name = "orbit-labs-tf-${count.index + 1}"
  image = docker_image.app.image_id
  env = ["DATABASE_URL=sqlite:////tmp/lab.db", "APP_VERSION=2.0.0", "DEPLOY_COLOR=terraform"]
}
output "replica_names" { value = docker_container.replica[*].name }
