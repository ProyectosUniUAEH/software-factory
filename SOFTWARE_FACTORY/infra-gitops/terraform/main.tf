# ==============================================================================
# MAIN TERRAFORM CONFIGURATION - KAANBAL ENGINE
# ==============================================================================
# Este módulo despliega un cluster K3s en AWS EC2 con:
# - ArgoCD para GitOps
# - Cert-Manager para certificados SSL automáticos
# - Nginx Ingress Controller para routing
# ==============================================================================

terraform {
  required_version = ">= 1.5.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.4"
    }
  }
  
  # Backend para estado remoto (opcional, descomentar para usar S3)
  # backend "s3" {
  #   bucket         = "terraform-state-software-factory"
  #   key            = "infrastructure/terraform.tfstate"
  #   region         = "us-east-2"
  #   encrypt        = true
  #   dynamodb_table = "terraform-locks"
  # }
}

# ------------------------------------------------------------------------------
# AWS Provider Configuration
# ------------------------------------------------------------------------------
provider "aws" {
  region     = var.aws_region
  # Usar credenciales si se proporcionan, de lo contrario usar perfil
  access_key = var.aws_access_key != "" ? var.aws_access_key : null
  secret_key = var.aws_secret_key != "" ? var.aws_secret_key : null
  profile    = var.aws_access_key == "" ? var.aws_profile : null
  
  default_tags {
    tags = local.common_tags
  }
}

# ------------------------------------------------------------------------------
# Data Sources
# ------------------------------------------------------------------------------

# Obtener la AMI más reciente de Ubuntu 22.04 LTS
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# Obtener la VPC por defecto
data "aws_vpc" "default" {
  default = true
}

# Obtener subnets de la VPC por defecto
data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# IP Elástica existente
data "aws_eip" "factory" {
  id = var.elastic_ip_allocation_id
}

# Availability Zones
data "aws_availability_zones" "available" {
  state = "available"
}

# ------------------------------------------------------------------------------
# SSH Key Pair
# ------------------------------------------------------------------------------
# Generar nuevo key pair (se guarda la private key localmente)
resource "tls_private_key" "ssh_key" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

resource "aws_key_pair" "factory" {
  key_name   = var.ssh_key_name
  public_key = tls_private_key.ssh_key.public_key_openssh
}

# Guardar la clave privada localmente (sobreescribe el .pem existente)
resource "local_file" "private_key" {
  content         = tls_private_key.ssh_key.private_key_pem
  filename        = var.ssh_private_key_path
  file_permission = "0600"
}

# ------------------------------------------------------------------------------
# Random Resources
# ------------------------------------------------------------------------------

# Generar contraseña de ArgoCD si no se proporciona
resource "random_password" "argocd_password" {
  count   = var.argocd_admin_password == "" ? 1 : 0
  length  = 16
  special = true
  override_special = "!@#$%"
}

# Token para K3s
resource "random_password" "k3s_token" {
  length  = 32
  special = false
}

# ------------------------------------------------------------------------------
# Security Group
# ------------------------------------------------------------------------------
resource "aws_security_group" "k3s_cluster" {
  name_prefix = "${var.project_name}-k3s-"
  description = "Security group for K3s cluster - KAANBAL ENGINE"
  vpc_id      = data.aws_vpc.default.id

  # SSH
  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.allowed_ssh_cidr]
  }

  # HTTP
  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # HTTPS
  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Kubernetes API
  ingress {
    description = "Kubernetes API"
    from_port   = 6443
    to_port     = 6443
    protocol    = "tcp"
    cidr_blocks = [var.allowed_ssh_cidr]
  }

  # NodePort range (opcional)
  ingress {
    description = "NodePort Services"
    from_port   = 30000
    to_port     = 32767
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Internal cluster traffic (K3s nodes, Flannel overlay, pod-to-pod)
  ingress {
    description = "Internal cluster traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    self        = true
  }

  # Egress - Allow all outbound traffic
  egress {
    description = "Allow all outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-k3s-sg"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# ------------------------------------------------------------------------------
# IAM Role & Instance Profile (Required for EBS CSI Driver)
# ------------------------------------------------------------------------------
resource "aws_iam_role" "k3s_role" {
  name = "${var.project_name}-k3s-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-iam-role"
  }
}

resource "aws_iam_role_policy_attachment" "ebs_csi_policy" {
  role       = aws_iam_role.k3s_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"
}

# KMS key for Vault auto-unseal
resource "aws_kms_key" "vault_unseal" {
  description             = "Vault auto-unseal key for ${var.project_name}"
  deletion_window_in_days = 7
  tags = {
    Name = "${var.project_name}-vault-unseal"
  }
}

resource "aws_kms_alias" "vault_unseal" {
  name          = "alias/${var.project_name}-vault-unseal"
  target_key_id = aws_kms_key.vault_unseal.key_id
}

# IAM policy: Vault KMS auto-unseal
resource "aws_iam_role_policy" "vault_kms_unseal" {
  name = "vault-kms-unseal"
  role = aws_iam_role.k3s_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["kms:Encrypt", "kms:Decrypt", "kms:DescribeKey"]
      Resource = [aws_kms_key.vault_unseal.arn]
    }]
  })
}

# IAM policy: Cluster Autoscaler
resource "aws_iam_role_policy" "cluster_autoscaler" {
  name = "cluster-autoscaler"
  role = aws_iam_role.k3s_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "autoscaling:DescribeAutoScalingGroups",
        "autoscaling:DescribeAutoScalingInstances",
        "autoscaling:DescribeLaunchConfigurations",
        "autoscaling:DescribeScalingActivities",
        "autoscaling:SetDesiredCapacity",
        "autoscaling:TerminateInstanceInAutoScalingGroup",
        "ec2:DescribeLaunchTemplateVersions",
        "ec2:DescribeInstanceTypes",
        "ec2:DescribeImages",
        "ec2:GetInstanceTypesFromInstanceRequirements"
      ]
      Resource = ["*"]
    }]
  })
}

resource "aws_iam_instance_profile" "k3s_profile" {
  name = "${var.project_name}-k3s-profile"
  role = aws_iam_role.k3s_role.name
}

# ------------------------------------------------------------------------------
# EC2 Instance - Master Node
# ------------------------------------------------------------------------------
resource "aws_instance" "k3s_master" {
  ami           = data.aws_ami.ubuntu.id
  instance_type = var.instance_type_override != "" ? var.instance_type_override : local.selected_profile.instance_type
  key_name      = var.ssh_key_name
  iam_instance_profile = aws_iam_instance_profile.k3s_profile.name
  
  vpc_security_group_ids = [aws_security_group.k3s_cluster.id]

  # Allow containers (pods) to access EC2 instance metadata (IMDS)
  metadata_options {
    http_endpoint               = "enabled"
    http_put_response_hop_limit = 2
    http_tokens                 = "optional"
  }

  root_block_device {
    volume_size           = var.root_volume_size > 0 ? var.root_volume_size : local.selected_profile.disk_size
    volume_type           = "gp3"
    encrypted             = true
    delete_on_termination = true
    
    tags = {
      Name = "${var.project_name}-root-volume"
    }
  }

  user_data = base64encode(templatefile("${path.module}/scripts/user-data.sh", {
    k3s_version             = var.k3s_version
    k3s_token               = random_password.k3s_token.result
    domain_name             = var.domain_name
    email_letsencrypt       = var.email_letsencrypt
    elastic_ip              = var.elastic_ip
    install_argocd          = var.install_argocd
    install_cert_manager    = var.install_cert_manager
    install_nginx_ingress   = var.install_nginx_ingress
    install_ebs_csi_driver  = var.install_ebs_csi_driver
    argocd_password         = var.argocd_admin_password != "" ? var.argocd_admin_password : (length(random_password.argocd_password) > 0 ? random_password.argocd_password[0].result : "")
    git_username            = var.git_username
    git_token               = var.git_token
    git_repo_url            = var.git_repo_url
    bitbucket_workspace     = var.bitbucket_workspace
    bitbucket_email         = var.bitbucket_email
    tailscale_client_id     = var.tailscale_client_id
    tailscale_client_secret = var.tailscale_client_secret
    tailscale_dns_suffix    = var.tailscale_dns_suffix
    docker_username         = var.docker_username
    docker_token            = var.docker_token
    vault_init_token        = var.vault_init_token
    vault_hostname          = var.vault_hostname
    project_name            = var.project_name
    aws_region              = var.aws_region
    kaanbal_admin_user        = var.kaanbal_admin_user
    kaanbal_admin_password    = var.kaanbal_admin_password
  }))

  tags = {
    Name = "${var.project_name}-k3s-master"
    Role = "master"
  }

  # Asegurar que el key pair existe antes de crear la instancia
  depends_on = [aws_key_pair.factory]

  lifecycle {
    ignore_changes = [user_data, ami]
  }
}

# ------------------------------------------------------------------------------
# Associate Elastic IP
# ------------------------------------------------------------------------------
resource "aws_eip_association" "k3s_master" {
  instance_id   = aws_instance.k3s_master.id
  allocation_id = var.elastic_ip_allocation_id
}

# ==============================================================================
# AUTO SCALING WORKERS CONFIGURATION
# ==============================================================================

# ------------------------------------------------------------------------------
# Launch Template for Worker Nodes
# ------------------------------------------------------------------------------
resource "aws_launch_template" "k3s_worker" {
  count = var.enable_autoscaling ? 1 : 0

  name_prefix   = "${var.project_name}-k3s-worker-"
  image_id      = data.aws_ami.ubuntu.id
  instance_type = var.worker_instance_type
  key_name      = var.ssh_key_name

  iam_instance_profile {
    name = aws_iam_instance_profile.k3s_profile.name
  }

  vpc_security_group_ids = [aws_security_group.k3s_cluster.id]

  # Allow containers (pods) to access EC2 instance metadata (IMDS)
  metadata_options {
    http_endpoint               = "enabled"
    http_put_response_hop_limit = 2
    http_tokens                 = "optional"
  }

  block_device_mappings {
    device_name = "/dev/sda1"
    ebs {
      volume_size           = 30
      volume_type           = "gp3"
      encrypted             = true
      delete_on_termination = true
    }
  }

  # Enable detailed monitoring for Auto Scaling metrics
  monitoring {
    enabled = true
  }

  user_data = base64encode(templatefile("${path.module}/scripts/worker-user-data.sh", {
    k3s_version = var.k3s_version
    k3s_token   = random_password.k3s_token.result
    master_ip   = aws_instance.k3s_master.private_ip
  }))

  tag_specifications {
    resource_type = "instance"
    tags = {
      Name = "${var.project_name}-k3s-worker"
      Role = "worker"
    }
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [aws_instance.k3s_master]
}

# ------------------------------------------------------------------------------
# Auto Scaling Group for Workers
# ------------------------------------------------------------------------------
resource "aws_autoscaling_group" "k3s_workers" {
  count = var.enable_autoscaling ? 1 : 0

  name                = "${var.project_name}-k3s-workers-asg"
  vpc_zone_identifier = data.aws_subnets.default.ids
  
  min_size         = var.worker_min_count
  max_size         = var.worker_max_count
  desired_capacity = max(var.worker_desired_count, var.worker_min_count)

  # Health check
  health_check_type         = "EC2"
  health_check_grace_period = 300

  # Use Launch Template
  launch_template {
    id      = aws_launch_template.k3s_worker[0].id
    version = "$Latest"
  }

  # Instance refresh for updates
  instance_refresh {
    strategy = "Rolling"
    preferences {
      min_healthy_percentage = 50
    }
  }

  tag {
    key                 = "Name"
    value               = "${var.project_name}-k3s-worker"
    propagate_at_launch = true
  }

  tag {
    key                 = "Role"
    value               = "worker"
    propagate_at_launch = true
  }

  tag {
    key                 = "kubernetes.io/cluster/${var.project_name}"
    value               = "owned"
    propagate_at_launch = true
  }

  tag {
    key                 = "k8s.io/cluster-autoscaler/enabled"
    value               = "true"
    propagate_at_launch = false
  }

  tag {
    key                 = "k8s.io/cluster-autoscaler/${var.project_name}"
    value               = "owned"
    propagate_at_launch = false
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [aws_instance.k3s_master]
}

# ------------------------------------------------------------------------------
# NOTE: CPU-based CloudWatch scaling policies removed.
# Scaling is now handled by Kubernetes Cluster Autoscaler which watches for
# Pending pods (resource-aware scaling) instead of EC2 CPU metrics.
# See user-data.sh for Cluster Autoscaler Helm install.
# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
# Local Files - Outputs útiles
# ------------------------------------------------------------------------------
resource "local_file" "cluster_info" {
  filename = "${path.module}/outputs/cluster-info.txt"
  content  = <<-EOT
    ================================================================================
    KAANBAL ENGINE - CLUSTER INFORMATION
    ================================================================================
    
    Fecha de creación: ${timestamp()}
    
    ACCESO AL CLUSTER:
    ------------------
    SSH: ssh -i <your-key> ubuntu@${var.elastic_ip}
    
    URLS DE SERVICIOS:
    ------------------
    ArgoCD:     https://argocd.${var.domain_name}
    
    CONFIGURACIÓN:
    --------------
    Perfil:          ${var.instance_profile}
    Tipo Instancia:  ${var.instance_type_override != "" ? var.instance_type_override : local.selected_profile.instance_type}
    Disco:           ${var.root_volume_size > 0 ? var.root_volume_size : local.selected_profile.disk_size} GB
    Región:          ${var.aws_region}
    IP Elástica:     ${var.elastic_ip}
    Dominio:         ${var.domain_name}
    
    KUBECTL:
    --------
    Para obtener el kubeconfig:
    scp -i <your-key> ubuntu@${var.elastic_ip}:/etc/rancher/k3s/k3s.yaml ./kubeconfig.yaml
    
    Luego editar el archivo y cambiar 127.0.0.1 por ${var.elastic_ip}
    
    ARGOCD LOGIN:
    -------------
    Usuario: admin
    Contraseña: Ver en terraform output argocd_password
    
    O usar CLI:
    argocd login argocd.${var.domain_name} --username admin --password <password>
    
    ================================================================================
  EOT

  depends_on = [aws_instance.k3s_master]
}
