# ==============================================================================
# VARIABLES DE CONFIGURACIÓN - KAANBAL ENGINE
# ==============================================================================

# ------------------------------------------------------------------------------
# AWS Configuration
# ------------------------------------------------------------------------------
variable "aws_region" {
  description = "Región de AWS donde se desplegará la infraestructura"
  type        = string
  default     = "us-east-2"
}

variable "aws_profile" {
  description = "Perfil de AWS CLI a utilizar"
  type        = string
  default     = "default"
}

variable "aws_access_key" {
  description = "AWS Access Key ID"
  type        = string
  default     = ""
  sensitive   = true
}

variable "aws_secret_key" {
  description = "AWS Secret Access Key"
  type        = string
  default     = ""
  sensitive   = true
}

# ------------------------------------------------------------------------------
# Elastic IP Configuration
# ------------------------------------------------------------------------------
variable "elastic_ip_allocation_id" {
  description = "ID de asignación de la IP elástica existente"
  type        = string
  default     = ""  # Must be set in terraform.tfvars
}

variable "elastic_ip" {
  description = "Dirección IP elástica"
  type        = string
  default     = ""  # Must be set in terraform.tfvars
}

# ------------------------------------------------------------------------------
# Domain Configuration
# ------------------------------------------------------------------------------
variable "domain_name" {
  description = "Dominio principal"
  type        = string
  default     = "futurefarms.mx"
}

variable "email_letsencrypt" {
  description = "Email para certificados Let's Encrypt"
  type        = string
}

# ------------------------------------------------------------------------------
# Environment Configuration
# ------------------------------------------------------------------------------
variable "environment" {
  description = "Ambiente de despliegue (dev, staging, prod)"
  type        = string
  default     = "prod"
  
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "El ambiente debe ser: dev, staging o prod."
  }
}

variable "project_name" {
  description = "Nombre del proyecto"
  type        = string
  default     = "software-factory"
}

# ------------------------------------------------------------------------------
# EC2 Instance Configuration - PERFILES PREDEFINIDOS
# ------------------------------------------------------------------------------
variable "instance_profile" {
  description = "Perfil de instancia: micro (pruebas), small (desarrollo), medium (staging), large (producción)"
  type        = string
  default     = "small"
  
  validation {
    condition     = contains(["micro", "small", "medium", "large", "xlarge"], var.instance_profile)
    error_message = "El perfil debe ser: micro, small, medium, large o xlarge."
  }
}

# Mapeo de perfiles a tipos de instancia
locals {
  instance_profiles = {
    micro = {
      instance_type = "t3.micro"
      description   = "1 vCPU, 1GB RAM - Solo pruebas mínimas"
      disk_size     = 20
      max_pods      = 10
    }
    small = {
      instance_type = "t3.small"
      description   = "2 vCPU, 2GB RAM - Desarrollo básico"
      disk_size     = 30
      max_pods      = 20
    }
    medium = {
      instance_type = "t3.medium"
      description   = "2 vCPU, 4GB RAM - Desarrollo/Staging"
      disk_size     = 50
      max_pods      = 40
    }
    large = {
      instance_type = "t3.large"
      description   = "2 vCPU, 8GB RAM - Producción ligera"
      disk_size     = 80
      max_pods      = 60
    }
    xlarge = {
      instance_type = "t3.xlarge"
      description   = "4 vCPU, 16GB RAM - Producción completa"
      disk_size     = 100
      max_pods      = 100
    }
  }
  
  selected_profile = local.instance_profiles[var.instance_profile]
}

# Override manual del tipo de instancia (opcional)
variable "instance_type_override" {
  description = "Override del tipo de instancia (deja vacío para usar el perfil)"
  type        = string
  default     = ""
}

variable "root_volume_size" {
  description = "Tamaño del volumen raíz en GB (0 para usar el del perfil)"
  type        = number
  default     = 0
}

# ------------------------------------------------------------------------------
# K3s Configuration
# ------------------------------------------------------------------------------
variable "k3s_version" {
  description = "Versión de K3s a instalar"
  type        = string
  default     = "v1.29.0+k3s1"
}

variable "enable_k3s_ha" {
  description = "Habilitar modo HA para K3s (requiere múltiples nodos)"
  type        = bool
  default     = false
}

# ------------------------------------------------------------------------------
# Auto Scaling Workers Configuration
# ------------------------------------------------------------------------------
variable "enable_autoscaling" {
  description = "Habilitar Auto Scaling de workers basado en CPU"
  type        = bool
  default     = true
}

variable "worker_min_count" {
  description = "Número mínimo de workers (Cluster Autoscaler maneja el escalado)"
  type        = number
  default     = 2
}

variable "worker_max_count" {
  description = "Número máximo de workers para escalar"
  type        = number
  default     = 5
  
  validation {
    condition     = var.worker_max_count >= 0 && var.worker_max_count <= 10
    error_message = "El máximo de workers debe estar entre 0 y 10."
  }
}

variable "worker_desired_count" {
  description = "Número deseado inicial de workers"
  type        = number
  default     = 0
}

variable "worker_instance_type" {
  description = "Tipo de instancia para workers"
  type        = string
  default     = "t3.medium"
}

variable "scale_up_cpu_threshold" {
  description = "Porcentaje de CPU para escalar hacia arriba (crear nuevo worker)"
  type        = number
  default     = 70
}

variable "scale_down_cpu_threshold" {
  description = "Porcentaje de CPU para escalar hacia abajo (eliminar worker)"
  type        = number
  default     = 30
}

variable "scale_cooldown" {
  description = "Segundos de espera entre acciones de escalado"
  type        = number
  default     = 300
}

# ------------------------------------------------------------------------------
# EBS Storage Configuration
# ------------------------------------------------------------------------------
variable "install_ebs_csi_driver" {
  description = "Instalar AWS EBS CSI Driver para volúmenes persistentes automáticos"
  type        = bool
  default     = true
}

variable "ebs_default_volume_type" {
  description = "Tipo de volumen EBS por defecto (gp3, gp2, io1, io2)"
  type        = string
  default     = "gp3"
}

variable "ebs_default_iops" {
  description = "IOPS por defecto para volúmenes gp3 (3000-16000)"
  type        = number
  default     = 3000
}

variable "ebs_default_throughput" {
  description = "Throughput por defecto para volúmenes gp3 en MB/s (125-1000)"
  type        = number
  default     = 125
}

# ------------------------------------------------------------------------------
# SSH Configuration
# ------------------------------------------------------------------------------
variable "ssh_key_name" {
  description = "Nombre del key pair de AWS para SSH"
  type        = string
}

variable "ssh_public_key_path" {
  description = "Ruta al archivo de llave pública SSH (dejar vacío si el key pair ya existe en AWS)"
  type        = string
  default     = ""
}

variable "allowed_ssh_cidr" {
  description = "CIDR permitido para conexiones SSH (tu IP pública)"
  type        = string
  default     = "0.0.0.0/0" # CAMBIAR por tu IP real en producción
}

# ------------------------------------------------------------------------------
# Application Configuration
# ------------------------------------------------------------------------------
variable "install_argocd" {
  description = "Instalar ArgoCD"
  type        = bool
  default     = true
}

variable "install_cert_manager" {
  description = "Instalar Cert-Manager para certificados SSL"
  type        = bool
  default     = true
}

variable "install_nginx_ingress" {
  description = "Instalar Nginx Ingress Controller"
  type        = bool
  default     = true
}

variable "argocd_admin_password" {
  description = "Contraseña de admin para ArgoCD (se generará una si no se proporciona)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "kaanbal_admin_user" {
  description = "Usuario administrador de Kaanbal Console (se crea automáticamente en el primer deploy)"
  type        = string
  default     = "admin"
}

variable "kaanbal_admin_password" {
  description = "Contraseña del administrador de Kaanbal Console"
  type        = string
  default     = ""
  sensitive   = true
}

# ------------------------------------------------------------------------------
# Tags
# ------------------------------------------------------------------------------
variable "tags" {
  description = "Tags adicionales para los recursos"
  type        = map(string)
  default     = {}
}

locals {
  common_tags = merge(
    {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
      Domain      = var.domain_name
    },
    var.tags
  )
}

# ------------------------------------------------------------------------------
# Git Configuration (Private Repo)
# ------------------------------------------------------------------------------
variable "git_username" {
  description = "Username para autenticación Git (Bitbucket)"
  type        = string
  default     = ""
}

variable "git_token" {
  description = "App Password/Token para autenticación Git"
  type        = string
  default     = ""
  sensitive   = true
}

variable "git_repo_url" {
  description = "URL del repositorio Git (HTTPS)"
  type        = string
  default     = "https://bitbucket.org/software-factory-iot/infra-gitops.git"
}

variable "bitbucket_workspace" {
  description = "Workspace slug de Bitbucket"
  type        = string
  default     = "software-factory-iot"
}

variable "bitbucket_email" {
  description = "Email para autenticación Bitbucket API (Basic auth)"
  type        = string
  default     = ""
}

# ------------------------------------------------------------------------------
# Tailscale Configuration
# ------------------------------------------------------------------------------
variable "tailscale_client_id" {
  description = "Tailscale OAuth Client ID"
  type        = string
  default     = ""
}

variable "tailscale_client_secret" {
  description = "Tailscale OAuth Client Secret"
  type        = string
  default     = ""
  sensitive   = true
}

variable "tailscale_dns_suffix" {
  description = "MagicDNS suffix de la red Tailscale (ej: tailXXXX.ts.net). Ver en https://login.tailscale.com/admin/dns"
  type        = string
  default     = ""
}

variable "ssh_private_key_path" {
  description = "Ruta al archivo de llave privada SSH (.pem)"
  type        = string
  default     = ""
}

# ------------------------------------------------------------------------------
# Vault Configuration
# ------------------------------------------------------------------------------
variable "vault_init_token" {
  description = "Root Token de Vault (dejar vacío en instalación inicial)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "vault_hostname" {
  description = "Hostname público de Vault (ej: vault.tudominio.com)"
  type        = string
  default     = ""
}

# ------------------------------------------------------------------------------
# Docker Hub Configuration
# ------------------------------------------------------------------------------
variable "docker_username" {
  description = "Docker Hub username for pushing images"
  type        = string
  default     = ""
}

variable "docker_token" {
  description = "Docker Hub access token"
  type        = string
  default     = ""
  sensitive   = true
}
