# ==============================================================================
# VAULT CONFIGURATION (CONDICIONAL)
# ==============================================================================
# Esta configuración es OPCIONAL y solo se aplica cuando:
#   1. Vault ya está desplegado (via ArgoCD)
#   2. Vault está inicializado y desellaod
#   3. Se proporciona vault_init_token en terraform.tfvars
#
# CICLO DE VIDA:
# ─────────────────────────────────────────────────────────────────────
# INSTALACIÓN LIMPIA (sin volúmenes previos):
#   1. terraform apply (vault_init_token = "")  → Crea infra, ignora Vault config
#   2. ArgoCD despliega Vault                   → Vault está sellado
#   3. vault operator init                      → Genera root token + unseal keys
#   4. Actualizar terraform.tfvars con token
#   5. terraform apply                          → Configura Vault
#
# RECOVERY (con volúmenes persistentes):
#   1. terraform apply (vault_init_token = "")  → Crea infra
#   2. ArgoCD re-despliega Vault con PVC        → Vault conserva datos
#   3. vault operator unseal                    → Usar keys guardadas
#   4. terraform apply (con token existente)    → Re-aplica config
# ─────────────────────────────────────────────────────────────────────

# Variable local para saber si configurar Vault
locals {
  configure_vault = var.vault_init_token != ""
}

provider "vault" {
  # Solo se usa si hay token configurado
  address         = var.vault_init_token != "" ? "https://vault.${var.domain_name}" : "https://localhost:8200"
  token           = var.vault_init_token
  skip_tls_verify = true
}

# ------------------------------------------------------------------------------
# SECRET ENGINES (solo si hay token)
# ------------------------------------------------------------------------------

resource "vault_mount" "kvv2" {
  count       = local.configure_vault ? 1 : 0
  path        = "secret"
  type        = "kv-v2"
  description = "Principal Store para Secretos de Kaanbal Engine"
}

# ------------------------------------------------------------------------------
# POLICIES (solo si hay token)
# ------------------------------------------------------------------------------

resource "vault_policy" "dev_read_policy" {
  count = local.configure_vault ? 1 : 0
  name  = "dev-read-only"

  policy = <<EOT
path "secret/data/dev/*" {
  capabilities = ["read", "list"]
}
EOT
}

# ------------------------------------------------------------------------------
# AUTH METHODS (solo si hay token)
# ------------------------------------------------------------------------------

resource "vault_auth_backend" "kubernetes" {
  count = local.configure_vault ? 1 : 0
  type  = "kubernetes"
}

resource "vault_kubernetes_auth_backend_config" "config" {
  count              = local.configure_vault ? 1 : 0
  backend            = vault_auth_backend.kubernetes[0].path
  kubernetes_host    = "https://kubernetes.default.svc"
  kubernetes_ca_cert = ""
}
