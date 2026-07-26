# ==============================================================================
# CLUSTER WORKERS CONFIGURATION - KAANBAL ENGINE
# ==============================================================================
# Configuración de workers para el CLUSTER CENTRAL
#
# El cluster central tiene:
#   - 1 Master (siempre EC2) - Control plane, ArgoCD, Ingress
#   - N Workers que pueden ser:
#     - EC2 (auto-scaling en AWS)
#     - Locales (tu PC, RPi conectados via Tailscale)
#
# IMPORTANTE: Los "clientes" (Edge) NO son workers de este cluster.
#             Son clusters K3s independientes gestionados por ArgoCD.
# ==============================================================================

# ------------------------------------------------------------------------------
# AWS Workers Configuration
# ------------------------------------------------------------------------------
variable "aws_workers" {
  description = "Configuración de workers en AWS EC2"
  type = object({
    enabled       = bool
    min_count     = number
    max_count     = number
    desired_count = number
    instance_type = string
  })
  default = {
    enabled       = true
    min_count     = 1
    max_count     = 5
    desired_count = 1
    instance_type = "t3.medium"
  }
}

# ------------------------------------------------------------------------------
# Local Workers Configuration (via Tailscale)
# ------------------------------------------------------------------------------
variable "local_workers" {
  description = <<-EOT
    Lista de workers locales que se conectarán via Tailscale.
    
    IMPORTANTE: Estos NO se crean automáticamente por Terraform.
    Terraform genera los scripts de conexión, pero TÚ debes:
    1. Instalar Tailscale en la máquina local
    2. Ejecutar el script de join generado
    
    Ejemplo:
    local_workers = [
      {
        name         = "mi-pc-ubuntu"
        tailscale_ip = ""  # Se llena después de conectar Tailscale
        type         = "ubuntu-pc"
        description  = "PC de desarrollo con Ubuntu"
      }
    ]
  EOT
  
  type = list(object({
    name         = string
    tailscale_ip = string
    type         = string
    description  = string
  }))
  
  default = []
}

# ------------------------------------------------------------------------------
# Computed Values
# ------------------------------------------------------------------------------
locals {
  has_aws_workers   = var.aws_workers.enabled && var.aws_workers.max_count > 0
  has_local_workers = length(var.local_workers) > 0
  
  ready_local_workers = [
    for w in var.local_workers : w if w.tailscale_ip != ""
  ]
  
  pending_local_workers = [
    for w in var.local_workers : w if w.tailscale_ip == ""
  ]
  
  workers_summary = {
    aws_workers = {
      enabled = local.has_aws_workers
      count   = local.has_aws_workers ? "${var.aws_workers.min_count}-${var.aws_workers.max_count}" : "0"
      type    = var.aws_workers.instance_type
    }
    local_workers = {
      configured = length(var.local_workers)
      ready      = length(local.ready_local_workers)
      pending    = length(local.pending_local_workers)
    }
  }
}

# ------------------------------------------------------------------------------
# Output: Workers Status
# ------------------------------------------------------------------------------
output "workers_configuration" {
  description = "Estado de la configuración de workers"
  value = {
    summary = local.workers_summary
    
    aws_workers = local.has_aws_workers ? {
      status        = "Enabled"
      auto_scaling  = "${var.aws_workers.min_count} - ${var.aws_workers.max_count} instances"
      instance_type = var.aws_workers.instance_type
    } : {
      status        = "Disabled"
      auto_scaling  = "N/A"
      instance_type = "N/A"
    }
    
    local_workers = {
      total   = length(var.local_workers)
      ready   = [for w in local.ready_local_workers : w.name]
      pending = [for w in local.pending_local_workers : "${w.name} (run join script)"]
      status  = length(var.local_workers) > 0 ? "Configured" : "None configured"
    }
  }
}

# ------------------------------------------------------------------------------
# Generate Worker Setup Instructions (Markdown)
# ------------------------------------------------------------------------------
resource "local_file" "worker_join_instructions" {
  filename = "${path.module}/outputs/WORKER-SETUP.md"
  
  content = <<-EOT
# Guia para Agregar Workers al Cluster Central

## Informacion del Cluster
- **Master IP**: ${var.elastic_ip}
- **K3s API**: https://${var.elastic_ip}:6443
- **Dominio**: ${var.domain_name}

---

## Workers en AWS EC2

${local.has_aws_workers ? "Habilitados - Auto-scaling: ${var.aws_workers.min_count} a ${var.aws_workers.max_count} instancias" : "Deshabilitados - Configura aws_workers.enabled = true"}

---

## Workers Locales (via Tailscale)

### Prerequisitos
1. Maquina con Ubuntu 22.04+ o Raspberry Pi OS 64-bit
2. Tailscale instalado y conectado a tu red
3. Acceso SSH al master (para obtener el token)

### Paso 1: Instalar Tailscale
```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
# Anota la IP que te asigna (100.x.x.x)
```

### Paso 2: Obtener Token del Master
```bash
ssh ubuntu@${var.elastic_ip} "sudo cat /var/lib/rancher/k3s/server/node-token"
```

### Paso 3: Instalar K3s como Worker
```bash
# Reemplaza <TOKEN> con el token del paso anterior
# Reemplaza <TAILSCALE_IP_MASTER> con la IP de Tailscale del master

curl -sfL https://get.k3s.io | K3S_URL=https://<TAILSCALE_IP_MASTER>:6443 K3S_TOKEN=<TOKEN> sh -
```

### Paso 4: Verificar Conexion
```bash
# En el master
kubectl get nodes
```

---

## Workers Locales Configurados

%{for w in var.local_workers~}
### ${w.name}
- **Tipo**: ${w.type}
- **Descripcion**: ${w.description}
- **Tailscale IP**: ${w.tailscale_ip != "" ? w.tailscale_ip : "Pendiente - ejecuta los pasos arriba"}
- **Estado**: ${w.tailscale_ip != "" ? "Listo para conectar" : "Pendiente de configuracion"}

%{endfor~}
%{if length(var.local_workers) == 0~}
*No hay workers locales configurados.*
%{endif~}

---

## Diferencia: Workers vs Clientes

| Concepto | Workers (Central) | Clientes (Edge) |
|----------|-------------------|-----------------|
| Que es? | Nodos del cluster AWS | Clusters independientes |
| Donde? | AWS o tu red local | Casa del cliente |
| Para que? | Correr apps centrales | IoT local del cliente |
| Offline? | No funciona sin master | Si, independiente |
| Datos | Volumenes AWS/EBS | Almacenamiento local |

EOT

  depends_on = [aws_instance.k3s_master]
}
