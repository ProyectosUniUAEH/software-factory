#!/usr/bin/env bash
# Re-siembra argocd_password, argocd_server, vault_addr y vault_token en la API.
# Útil tras corregir I-02/I-03 en un cluster ya instalado.
set -euo pipefail
tr -d '\r' < /etc/kaanbal/installer.env > /tmp/kb-installer.env
set -a
source /tmp/kb-installer.env
set +a

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/installer"
export PYTHONPATH="$ROOT/installer"

python3 << 'PY'
import json
import base64
import sys
import os

sys.path.insert(0, ".")
import server

token = server.bootstrap_vault_lab(server.kubectl, log_fn=print)
if not token:
    token = server.read_vault_root_token(server.kubectl)

rc, argo_b64 = server.kubectl(
    "-n argocd get secret argocd-initial-admin-secret "
    "-o jsonpath='{.data.password}'", stream=False)
argo_pwd = ""
if rc == 0 and argo_b64.strip():
    argo_pwd = base64.b64decode(argo_b64.strip().strip("'")).decode()

# Resolve GitHub login even when installer.env has no GITHUB_LOGIN
cfg = {
    "mode": os.environ.get("KAANBAL_MODE") or os.environ.get("MODE") or "cloud",
    "domain": os.environ.get("DOMAIN", "").lower(),
    "github_org": os.environ.get("GITHUB_ORG", ""),
    "gitops_token": os.environ.get("GITOPS_TOKEN", ""),
    "github_login": (
        os.environ.get("GITHUB_LOGIN")
        or os.environ.get("GITHUB_USER")
        or ""
    ),
    "docker_user": os.environ.get("DOCKER_USER", ""),
    "docker_token": os.environ.get("DOCKER_TOKEN", ""),
    "tailscale_id": os.environ.get("TAILSCALE_CLIENT_ID", ""),
    "tailscale_secret": os.environ.get("TAILSCALE_CLIENT_SECRET", ""),
    "tailscale_dns": os.environ.get("TAILSCALE_DNS_SUFFIX", ""),
    "cf_token": os.environ.get("CF_TOKEN", ""),
    "cf_account": os.environ.get("CF_ACCOUNT_ID", ""),
    "admin_user": os.environ.get("KAANBAL_ADMIN_USER", "admin"),
    "admin_pass": os.environ.get("KAANBAL_ADMIN_PASS", "admin"),
}
ok, detail = server.seed_platform(cfg, argo_pwd, log_fn=print, vault_token=token)
if not ok:
    print("SEED_FAILED", detail)
    sys.exit(1)
print("SEED_OK")
PY
