# ==============================================================================
# TAILSCALE KUBERNETES OPERATOR - TERRAFORM CONFIGURATION
# ==============================================================================
# Este archivo configura:
# 1. El Secret OAuth del operador en el cluster K8s
# 2. Los tags ACL requeridos por la plataforma (tag:database, tag:iot, etc.)
#
# Prerequisitos en Tailscale Admin Console:
# 1. Crear tags base en ACL: tag:k8s-operator y tag:k8s (ownership: autogroup:admin)
# 2. Crear OAuth Client con scopes: Devices Write, Auth Keys Write, ACL Read/Write
# 3. Copiar Client ID y Secret a terraform.tfvars
#
# Tags de plataforma (tag:database, tag:iot) se configuran automáticamente
# al ejecutar terraform apply. El operador (tag:k8s-operator) será owner
# de estos tags para poder asignarlos a los servicios que expone.
# ==============================================================================

# --- Locals: Tags requeridos por la plataforma ---
# Estos tags se sincronizan al ACL de Tailscale automáticamente.
# Si se agrega un nuevo tag en catalog.json, agregarlo aquí también.
locals {
  tailscale_platform_tags = ["tag:database", "tag:iot"]
}

# --- 1. Operator Secret en K8s ---
resource "null_resource" "tailscale_operator_secret" {
  count = var.tailscale_client_id != "" && var.tailscale_client_secret != "" ? 1 : 0

  depends_on = [aws_instance.k3s_master]

  provisioner "remote-exec" {
    connection {
      type        = "ssh"
      user        = "ubuntu"
      private_key = file(var.ssh_private_key_path)
      host        = var.elastic_ip
    }

    inline = [
      "echo '🔐 Configurando Tailscale Operator Secret...'",
      "kubectl create namespace tailscale --dry-run=client -o yaml | kubectl apply -f -",
      "kubectl create secret generic operator-oauth \\",
      "  --namespace tailscale \\",
      "  --from-literal=client_id='${var.tailscale_client_id}' \\",
      "  --from-literal=client_secret='${var.tailscale_client_secret}' \\",
      "  --dry-run=client -o yaml | kubectl apply -f -",
      "echo '✅ Tailscale Operator Secret configurado correctamente'"
    ]
  }

  triggers = {
    client_id_hash = sha256(var.tailscale_client_id)
  }
}

# --- 2. Configurar ACL Tags via Tailscale API ---
# Obtiene un token OAuth, lee el ACL actual, y agrega los tags
# de plataforma si no existen. Esto evita que deployments de bases
# de datos fallen con "requested tags [tag:database] are invalid".
resource "null_resource" "tailscale_acl_tags" {
  count = var.tailscale_client_id != "" && var.tailscale_client_secret != "" ? 1 : 0

  depends_on = [null_resource.tailscale_operator_secret]

  provisioner "local-exec" {
    interpreter = ["PowerShell", "-Command"]
    command     = <<-EOT
      $ErrorActionPreference = 'Stop'

      # 1. Obtener OAuth token
      $body = "client_id=${var.tailscale_client_id}&client_secret=${var.tailscale_client_secret}&grant_type=client_credentials"
      $tokenResp = Invoke-RestMethod -Uri "https://api.tailscale.com/api/v2/oauth/token" -Method POST -Body $body -ContentType "application/x-www-form-urlencoded"
      $headers = @{ "Authorization" = "Bearer $($tokenResp.access_token)"; "Content-Type" = "application/json" }

      # 2. Leer ACL actual
      $acl = Invoke-RestMethod -Uri "https://api.tailscale.com/api/v2/tailnet/-/acl" -Method GET -Headers $headers

      # 3. Verificar si los tags de plataforma ya existen
      $platformTags = @(${join(", ", [for t in local.tailscale_platform_tags : "\"${t}\""])})
      $existingTags = @($acl.tagOwners.PSObject.Properties.Name)
      $missing = $platformTags | Where-Object { $_ -notin $existingTags }

      if ($missing.Count -eq 0) {
        Write-Host "✅ Todos los tags de plataforma ya existen en el ACL: $($platformTags -join ', ')"
        exit 0
      }

      Write-Host "📝 Tags faltantes: $($missing -join ', '). Actualizando ACL..."

      # 4. Agregar tags faltantes (owner = tag:k8s-operator)
      $tagOwners = @{}
      foreach ($prop in $acl.tagOwners.PSObject.Properties) {
        $tagOwners[$prop.Name] = @($prop.Value)
      }
      foreach ($tag in $missing) {
        $tagOwners[$tag] = @("tag:k8s-operator")
      }

      # 5. Reconstruir ACL con tags nuevos + ACL rules existentes
      $newAcl = @{
        tagOwners = $tagOwners
        acls      = @($acl.acls)
      }
      # Preservar campos opcionales si existen
      if ($acl.PSObject.Properties['ssh']) { $newAcl.ssh = $acl.ssh }
      if ($acl.PSObject.Properties['autoApprovers']) { $newAcl.autoApprovers = $acl.autoApprovers }
      if ($acl.PSObject.Properties['nodeAttrs']) { $newAcl.nodeAttrs = $acl.nodeAttrs }

      $jsonBody = $newAcl | ConvertTo-Json -Depth 10 -Compress
      Invoke-RestMethod -Uri "https://api.tailscale.com/api/v2/tailnet/-/acl" -Method POST -Headers $headers -Body $jsonBody | Out-Null

      Write-Host "✅ ACL actualizado. Tags agregados: $($missing -join ', ')"
    EOT
  }

  triggers = {
    # Re-ejecutar si cambian los tags de plataforma
    platform_tags_hash = sha256(join(",", local.tailscale_platform_tags))
  }
}

# Output para verificar estado
output "tailscale_operator_configured" {
  description = "Indica si el Tailscale Operator está configurado"
  value       = var.tailscale_client_id != "" ? "Configured" : "Not configured (missing credentials)"
}

output "tailscale_platform_tags" {
  description = "Tags de plataforma configurados en el ACL"
  value       = local.tailscale_platform_tags
}
