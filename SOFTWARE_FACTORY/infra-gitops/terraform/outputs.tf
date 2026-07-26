# ==============================================================================
# TERRAFORM OUTPUTS - KAANBAL ENGINE
# ==============================================================================

# ------------------------------------------------------------------------------
# Instance Information
# ------------------------------------------------------------------------------
output "instance_id" {
  description = "ID de la instancia EC2 master"
  value       = aws_instance.k3s_master.id
}

output "instance_public_ip" {
  description = "IP pública (Elastic IP) de la instancia"
  value       = var.elastic_ip
}

output "instance_private_ip" {
  description = "IP privada de la instancia master"
  value       = aws_instance.k3s_master.private_ip
}

output "instance_type" {
  description = "Tipo de instancia EC2"
  value       = aws_instance.k3s_master.instance_type
}

# ------------------------------------------------------------------------------
# Instance Profile Information
# ------------------------------------------------------------------------------
output "instance_profile_used" {
  description = "Perfil de instancia utilizado"
  value = {
    profile     = var.instance_profile
    description = local.selected_profile.description
    disk_size   = var.root_volume_size > 0 ? var.root_volume_size : local.selected_profile.disk_size
  }
}

# ------------------------------------------------------------------------------
# SSH Access
# ------------------------------------------------------------------------------
output "ssh_command" {
  description = "Comando SSH para conectarse a la instancia"
  value       = "ssh -i <path-to-key> ubuntu@${var.elastic_ip}"
}

# ------------------------------------------------------------------------------
# URLs
# ------------------------------------------------------------------------------
output "argocd_url" {
  description = "URL de ArgoCD"
  value       = var.install_argocd ? "https://argocd.${var.domain_name}" : "ArgoCD no instalado"
}

output "domain_info" {
  description = "Información del dominio"
  value = {
    domain        = var.domain_name
    argocd        = "argocd.${var.domain_name}"
    example_app   = "myapp.${var.domain_name}"
    example_dev   = "dev-myapp.${var.domain_name}"
  }
}

# ------------------------------------------------------------------------------
# ArgoCD Credentials
# ------------------------------------------------------------------------------
output "argocd_password" {
  description = "Contraseña de admin de ArgoCD"
  value       = nonsensitive(var.argocd_admin_password != "" ? var.argocd_admin_password : (length(random_password.argocd_password) > 0 ? random_password.argocd_password[0].result : "Ver en cluster: kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d"))
  sensitive   = false
}

output "argocd_login_info" {
  description = "Información de login de ArgoCD"
  value       = <<-EOT
    Usuario: admin
    URL: https://argocd.${var.domain_name}
    
    Para obtener la contraseña inicial:
    kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d
    
    O usar:
    terraform output argocd_password
  EOT
}

# ------------------------------------------------------------------------------
# Kubeconfig
# ------------------------------------------------------------------------------
output "kubeconfig_instructions" {
  description = "Instrucciones para obtener el kubeconfig"
  value       = <<-EOT
    1. Copiar el kubeconfig:
       scp -i <your-key> ubuntu@${var.elastic_ip}:/etc/rancher/k3s/k3s.yaml ./kubeconfig.yaml
    
    2. Editar el archivo y cambiar:
       server: https://127.0.0.1:6443
       por:
       server: https://${var.elastic_ip}:6443
    
    3. Usar:
       export KUBECONFIG=./kubeconfig.yaml
       kubectl get nodes
  EOT
}

# ------------------------------------------------------------------------------
# Worker Nodes Information
# ------------------------------------------------------------------------------
output "autoscaling_info" {
  description = "Información del Auto Scaling de Workers"
  value = var.enable_autoscaling ? {
    enabled          = true
    min_workers      = var.worker_min_count
    max_workers      = var.worker_max_count
    desired_workers  = var.worker_desired_count
    scale_up_at      = "${var.scale_up_cpu_threshold}% CPU"
    scale_down_at    = "${var.scale_down_cpu_threshold}% CPU"
    worker_type      = var.worker_instance_type
    asg_name         = aws_autoscaling_group.k3s_workers[0].name
  } : {
    enabled          = false
    min_workers      = 0
    max_workers      = 0
    desired_workers  = 0
    scale_up_at      = "N/A"
    scale_down_at    = "N/A"
    worker_type      = "N/A"
    asg_name         = "N/A"
  }
}

# ------------------------------------------------------------------------------
# EBS Storage Information
# ------------------------------------------------------------------------------
output "storage_info" {
  description = "Información del almacenamiento EBS"
  value = var.install_ebs_csi_driver ? {
    ebs_csi_driver   = "Installed"
    default_class    = "ebs-gp3"
    available_classes = [
      "ebs-gp3 (default) - General purpose, auto-delete",
      "ebs-gp3-retain - General purpose, keeps data",
      "ebs-io2-high-perf - High IOPS for databases"
    ]
    volume_type      = var.ebs_default_volume_type
    iops             = var.ebs_default_iops
    throughput       = "${var.ebs_default_throughput} MB/s"
  } : {
    ebs_csi_driver   = "Not installed"
    default_class    = "local-path"
    available_classes = ["local-path (data lost if node dies)"]
    volume_type      = "N/A"
    iops             = 0
    throughput       = "N/A"
  }
}

# ------------------------------------------------------------------------------
# Security Group
# ------------------------------------------------------------------------------
output "security_group_id" {
  description = "ID del Security Group"
  value       = aws_security_group.k3s_cluster.id
}

# ------------------------------------------------------------------------------
# K3s Token (para añadir workers manualmente)
# ------------------------------------------------------------------------------
output "k3s_token" {
  description = "Token de K3s para unir workers"
  value       = random_password.k3s_token.result
  sensitive   = true
}

output "vault_kms_key_id" {
  description = "KMS key ID for Vault auto-unseal"
  value       = aws_kms_key.vault_unseal.key_id
}

# ------------------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------------------
output "deployment_summary" {
  description = "Resumen del despliegue"
  value       = <<-EOT
    
    ╔══════════════════════════════════════════════════════════════════════════╗
    ║                      KAANBAL ENGINE DEPLOYED                           ║
    ╠══════════════════════════════════════════════════════════════════════════╣
    ║                                                                          ║
    ║  CLUSTER INFO:                                                           ║
    ║    K3s: ${var.k3s_version}
    ║    Master: ${var.instance_type_override != "" ? var.instance_type_override : local.selected_profile.instance_type} (${var.instance_profile})
    ║    Disk: ${var.root_volume_size > 0 ? var.root_volume_size : local.selected_profile.disk_size} GB
    ║    IP: ${var.elastic_ip}
    ║    Domain: ${var.domain_name}
    ║                                                                          ║
    ║  AUTO SCALING:                                                           ║
    ║    Enabled: ${var.enable_autoscaling}
    ║    Workers: min=${var.worker_min_count} / max=${var.worker_max_count}
    ║    Scale UP: CPU > ${var.scale_up_cpu_threshold}%
    ║    Scale DOWN: CPU < ${var.scale_down_cpu_threshold}%
    ║                                                                          ║
    ║  STORAGE (EBS CSI):                                                      ║
    ║    Enabled: ${var.install_ebs_csi_driver}
    ║    Default Class: ebs-gp3 (auto-provisioned AWS volumes)
    ║                                                                          ║
    ║  SERVICES:                                                               ║
    ║    ✓ Nginx Ingress Controller                                            ║
    ║    ✓ Cert-Manager (Let's Encrypt)                                        ║
    ║    ✓ ArgoCD                                                              ║
    ║    ✓ AWS EBS CSI Driver                                                  ║
    ║                                                                          ║
    ║  URLS:                                                                   ║
    ║    ArgoCD: https://argocd.${var.domain_name}
    ║                                                                          ║
    ╚══════════════════════════════════════════════════════════════════════════╝
    
  EOT
}
