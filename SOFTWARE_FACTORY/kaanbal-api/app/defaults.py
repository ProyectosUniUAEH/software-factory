"""
Kaanbal API - Centralized Defaults
=================================
Single source of truth for ALL default/fallback values used across the application.
Services should import from here instead of scattering magic strings.

These are FALLBACK values only. In production, values come from:
  1. MongoDB system_config (highest priority)
  2. Environment variables
  3. These defaults (lowest priority)
"""

# -- Database --
MONGODB_URI = "mongodb://datastore:27017/forge"

# -- Security --
SECRET_KEY_DEV = "supersecretkey_dev_only"
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 hours

# -- Vault --
VAULT_ADDR = "http://vault.vault.svc.cluster.local:8200"
VAULT_HOSTNAME = "vault-vault-ui-ingress"

# -- Tailscale --
# Fallback only. In production this should come from MongoDB system_config.
TAILSCALE_DNS_SUFFIX = "taildd8884.ts.net"
TAILSCALE_API_BASE = "https://api.tailscale.com/api/v2"
TAILSCALE_OAUTH_URL = "https://api.tailscale.com/api/v2/oauth/token"

# -- ArgoCD --
# Use in-cluster DNS name instead of fixed ClusterIP (IP changes per deploy)
# HTTP because helm installs ArgoCD with server.insecure=true (no TLS inside cluster)
ARGOCD_SERVER = "http://argocd-server.argocd.svc.cluster.local"
ARGOCD_USERNAME = "admin"

# -- Workspace --
WORKSPACE_PATH = "/tmp/kaanbal-workdir"
TEMPLATES_REPO = "kaanbal-templates"

# -- Pipeline --
PIPELINE_EMAIL_DOMAIN_FALLBACK = "kaanbal.local"
PIPELINE_GIT_USER = "Kaanbal Engine"

# -- Activity Logs --
LOG_RETENTION_DAYS = 90
LOG_FORWARDING_TIMEOUT_SEC = 5
LOG_FORWARDING_MIN_LEVEL = "error"

# -- Bitbucket API --
BITBUCKET_API_BASE = "https://api.bitbucket.org"

# -- GitHub API --
GITHUB_API_BASE = "https://api.github.com"

# -- Exposure Rules --
# Allowed exposure types per template category (enforced in deployer + UI)
# Per-environment model: each env selects ONE mode (internal/tailscale/public).
# 'both' is a computed aggregate (mixed envs) - not a selectable option.
# frontend:   public or VPN (internal makes no sense for a UI)
# backend:    internal, VPN, or public (full flexibility)
# database:   internal or VPN (never expose publicly)
# monitoring: VPN only
# devtools:   VPN only
# workflow:   VPN or public (webhooks need public)
# iot:        internal, VPN, or public
EXPOSURE_RULES = {
    "frontend":   ["public", "tailscale"],          # UI: public or VPN (no internal, no 'both')
    "backend":    ["internal", "tailscale", "public"], # APIs: full flexibility per-env
    "database":   ["internal", "tailscale"],           # DBs: NEVER expose publicly
    "monitoring": ["tailscale"],                       # Admin: VPN only
    "devtools":   ["tailscale"],                       # Admin: VPN only
    "workflow":   ["tailscale", "public"],             # n8n: webhooks=public, UI=VPN
    "iot":        ["internal", "tailscale", "public"],  # IoT: all single modes
}
EXPOSURE_RULES_DEFAULT = ["internal", "tailscale", "public"]
