#!/usr/bin/env bash
# Repara el cluster lab ya instalado (sin reinstall completo).
# Ejecutar en segundo plano:
#   nohup sudo bash tools/repair-lab.sh >> logs/repair-lab.log 2>&1 &
#   tail -f logs/repair-lab.log
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"
STAMP="$(date +%Y%m%d-%H%M%S)"
LOG="$LOG_DIR/repair-lab-$STAMP.log"
exec > >(tee -a "$LOG") 2>&1

log() { echo "[$(date -Iseconds)] $*"; }

log "=== repair-lab inicio ==="
log "ROOT=$ROOT"

if [ ! -f /etc/kaanbal/installer.env ]; then
  log "ERROR: falta /etc/kaanbal/installer.env"
  exit 1
fi

tr -d '\r' < /etc/kaanbal/installer.env > /tmp/kb-installer.env
set -a
# shellcheck disable=SC1091
source /tmp/kb-installer.env
set +a

ORG="${GITHUB_ORG:-ProyectosUniUAEH}"
TOKEN="${GITOPS_TOKEN:-}"
DOCKER_USER="${DOCKER_USER:-}"
DOCKER_TOKEN="${DOCKER_TOKEN:-}"

if [ -z "$TOKEN" ] || [ -z "$DOCKER_USER" ]; then
  log "ERROR: GITOPS_TOKEN o DOCKER_USER vacíos"
  exit 1
fi

export TOKEN ORG DOCKER_USER DOCKER_TOKEN

# --- 1. Re-sembrar plataforma (Vault + ArgoCD password en MongoDB) ---
log "--- paso 1: fix-platform-seed ---"
if [ -x "$ROOT/tools/fix-platform-seed.sh" ]; then
  bash "$ROOT/tools/fix-platform-seed.sh" && log "fix-platform-seed OK" || log "fix-platform-seed FALLÓ (continuando)"
else
  log "AVISO: no existe fix-platform-seed.sh"
fi

# --- 2. Publicar parches kaanbal-api a GitHub y construir imagen ---
log "--- paso 2: push kaanbal-api + build Kaniko ---"
cd "$ROOT/installer"
python3 << 'PY'
import os, sys, tempfile, shutil, subprocess
sys.path.insert(0, os.getcwd())
import gitops_publish
from server import run, kubectl, apply_yaml
import corebuild

token = os.environ["TOKEN"]
org = os.environ["ORG"]
docker_user = os.environ["DOCKER_USER"]
docker_token = os.environ["DOCKER_TOKEN"]
api_src = os.path.join(os.path.dirname(os.getcwd()), "kaanbal-api")

def log(msg):
    print(f"[push-api] {msg}", flush=True)

work = tempfile.mkdtemp(prefix="kaanbal-api-push-")
clone = os.path.join(work, "repo")
auth = gitops_publish.auth_url(token, org, "kaanbal-api")
rc, out = run(f"git clone --depth 1 '{auth}' '{clone}'", timeout=120)
if rc != 0:
    log(f"clone falló: {out[:300]}")
    sys.exit(1)

for item in ("app/defaults.py", "app/services/argocd_service.py", "app/routers/setup.py"):
    src = os.path.join(api_src, item)
    dst = os.path.join(clone, item)
    if os.path.isfile(src):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        log(f"copiado {item}")

rc, out = run(
    f"cd '{clone}' && git config user.email 'repair@kaanbal.local' "
    f"&& git config user.name 'Kaanbal Repair' && git add -A "
    f"&& git diff --cached --quiet || git commit -m 'fix: ArgoCD HTTPS auth + seed vault/argocd server'",
    timeout=60)
if rc != 0 and "nothing to commit" not in (out or ""):
    log(f"commit falló: {out[:300]}")
    sys.exit(1)

rc, out = run(f"cd '{clone}' && git push origin main", timeout=120)
if rc != 0:
    log(f"push falló: {out[:300]}")
    sys.exit(1)

rc, sha = run(f"cd '{clone}' && git rev-parse HEAD")
sha = (sha or "").strip()
tag = f"prod-{sha[:7]}"
log(f"push OK sha={sha[:7]} tag={tag}")

tags = {"kaanbal-api": tag}
log("construyendo imagen con Kaniko…")
corebuild.build_core_images(
    kubectl, apply_yaml,
    github_org=org, github_token=token,
    docker_user=docker_user, docker_token=docker_token,
    tags=tags,
    components=[c for c in corebuild.CORE_COMPONENTS if c["name"] == "kaanbal-api"],
    log_fn=lambda m, l="info": log(f"[{l}] {m}"),
)
log(f"imagen publicada {docker_user}/kaanbal-api:{tag}")

# Actualizar overlay prod en infra-gitops local renderizado vía git push
infra_work = tempfile.mkdtemp(prefix="kaanbal-infra-push-")
infra_clone = os.path.join(infra_work, "infra")
auth_infra = gitops_publish.auth_url(token, org, "infra-gitops")
rc, out = run(f"git clone --depth 1 '{auth_infra}' '{infra_clone}'", timeout=120)
if rc == 0:
    kust = os.path.join(infra_clone, "apps/kaanbal-api/overlays/prod/kustomization.yaml")
    if os.path.isfile(kust):
        import re
        text = open(kust, encoding="utf-8").read()
        text = re.sub(r"newTag:\s*\S+", f"newTag: {tag}", text)
        text = re.sub(r"newName:\s*\S+", f"newName: {docker_user}/kaanbal-api", text, count=1)
        open(kust, "w", encoding="utf-8").write(text)
        run(f"cd '{infra_clone}' && git config user.email 'repair@kaanbal.local' "
            f"&& git config user.name 'Kaanbal Repair' && git add -A "
            f"&& git commit -m 'fix: kaanbal-api {tag} (ArgoCD auth)' || true", timeout=60)
        rc, out = run(f"cd '{infra_clone}' && git push origin main", timeout=120)
        log(f"infra-gitops push: rc={rc} {(out or '')[:120]}")
PY

log "--- paso 3: esperar rollout kaanbal-api ---"
for i in $(seq 1 36); do
  ready=$(sudo k3s kubectl -n prod get deploy kaanbal-api -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo 0)
  desired=$(sudo k3s kubectl -n prod get deploy kaanbal-api -o jsonpath='{.spec.replicas}' 2>/dev/null || echo 1)
  img=$(sudo k3s kubectl -n prod get deploy kaanbal-api -o jsonpath='{.spec.template.spec.containers[0].image}' 2>/dev/null)
  log "rollout intento $i: ready=$ready/$desired image=$img"
  if [ "$ready" = "$desired" ] && [ "$ready" != "0" ]; then
    break
  fi
  sleep 10
done

sudo k3s kubectl -n prod rollout status deploy/kaanbal-api --timeout=120s || log "AVISO: rollout timeout"

# --- 4. Verificaciones ---
log "--- paso 4: verificaciones ---"
argo_app_count="$(sudo k3s kubectl -n argocd get applications --no-headers 2>/dev/null | wc -l | tr -d ' ')"
log "ArgoCD applications (kubectl): ${argo_app_count}"

if [ -x "$ROOT/tools/verify-platform-api-sudo.sh" ]; then
  bash "$ROOT/tools/verify-platform-api-sudo.sh" 2>&1 | while read -r line; do log "api: $line"; done \
    && log "verify-platform-api OK" || log "verify-platform-api FALLÓ"
elif [ -f /tmp/verify-platform-api-sudo.sh ]; then
  sudo bash /tmp/verify-platform-api-sudo.sh 2>&1 | while read -r line; do log "api: $line"; done \
    && log "verify-platform-api OK" || log "verify-platform-api FALLÓ"
else
  log "AVISO: no existe verify-platform-api-sudo.sh"
fi

sudo k3s kubectl -n vault exec deploy/vault -- vault status 2>&1 | head -6 | while read -r line; do log "vault: $line"; done

curl -sS -o /dev/null -w "api_health:%{http_code}\n" https://kaanbal-api.softwarefactory.site/health 2>/dev/null | while read -r line; do log "http: $line"; done

log "=== repair-lab fin ==="
log "Log completo: $LOG"
