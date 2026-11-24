# Kubernetes nodes: HTTP(S) and NodePorts from anywhere, admin ports only from admin_cidr,
# all traffic between nodes inside the VPC.
resource "aws_security_group" "cluster" {
  name        = "${var.name}-cluster-sg"
  description = "Kubernetes cluster nodes"
  vpc_id      = var.vpc_id

  tags = { Name = "${var.name}-cluster-sg" }
}

resource "aws_vpc_security_group_ingress_rule" "cluster_internal" {
  security_group_id = aws_security_group.cluster.id
  description       = "Node-to-node traffic inside the VPC"
  cidr_ipv4         = var.vpc_cidr
  ip_protocol       = "-1"
}

resource "aws_vpc_security_group_ingress_rule" "cluster_public" {
  for_each = { http = 80, https = 443 }

  security_group_id = aws_security_group.cluster.id
  description       = "Public ${each.key}"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "tcp"
  from_port         = each.value
  to_port           = each.value
}

resource "aws_vpc_security_group_ingress_rule" "cluster_nodeports" {
  security_group_id = aws_security_group.cluster.id
  description       = "NodePort services (ingress, Grafana, Kibana) - admin only"
  cidr_ipv4         = var.admin_cidr
  ip_protocol       = "tcp"
  from_port         = 30000
  to_port           = 32767
}

resource "aws_vpc_security_group_ingress_rule" "cluster_admin" {
  for_each = { ssh = 22, kube_api = 6443 }

  security_group_id = aws_security_group.cluster.id
  description       = "Admin ${each.key}"
  cidr_ipv4         = var.admin_cidr
  ip_protocol       = "tcp"
  from_port         = each.value
  to_port           = each.value
}

resource "aws_vpc_security_group_egress_rule" "cluster_all" {
  security_group_id = aws_security_group.cluster.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

# CI server: Jenkins + SonarQube.
resource "aws_security_group" "ci" {
  name        = "${var.name}-ci-sg"
  description = "Jenkins and SonarQube"
  vpc_id      = var.vpc_id

  tags = { Name = "${var.name}-ci-sg" }
}

resource "aws_vpc_security_group_ingress_rule" "ci_admin" {
  for_each = { ssh = 22, jenkins = 8081, sonarqube = 9000 }

  security_group_id = aws_security_group.ci.id
  description       = "Admin ${each.key}"
  cidr_ipv4         = var.admin_cidr
  ip_protocol       = "tcp"
  from_port         = each.value
  to_port           = each.value
}

# GitHub must reach the Jenkins webhook endpoint; restrict to GitHub's hook ranges.
resource "aws_vpc_security_group_ingress_rule" "ci_github_hooks" {
  for_each = toset(var.github_hook_cidrs)

  security_group_id = aws_security_group.ci.id
  description       = "GitHub webhooks"
  cidr_ipv4         = each.value
  ip_protocol       = "tcp"
  from_port         = 8081
  to_port           = 8081
}

resource "aws_vpc_security_group_egress_rule" "ci_all" {
  security_group_id = aws_security_group.ci.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}
