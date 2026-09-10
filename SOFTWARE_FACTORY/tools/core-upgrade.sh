#!/usr/bin/env bash
# ==============================================================================
# core-upgrade.sh — actualiza el engine de una célula ya instalada (ADR-002)
# ==============================================================================
# Versión manual y auditable de la transacción descrita en el ADR. Se ejecuta
# EN EL NODO de la célula. El token de GitHub sale del Secret del cluster y
# nunca se imprime ni sale del nodo.
#
#   lock → preflight → snapshot → sync → build → promote → verify
#                          └──────── rollback ────────┘
#
# Uso:
#   sudo bash core-upgrade.sh --ref main                 # actualizar
#   sudo bash core-upgrade.sh --snapshot                 # solo ver el estado
#   sudo bash core-upgrade.sh --rollback <api_tag> <console_tag>
#
# Por qué existe además del servicio: cuando el upgrade automático falla, hace
# falta una ruta que no dependa de la API que se está reemplazando.
set -euo pipefail

NS=prod
SOURCE_DIR=${KAANBAL_SOURCE:-/home/pam/kaanbal-source}
COMPONENTS=(kaanbal-api kaanbal-console)
REF=main
MODE=upgrade

while (($#)); do
  case "$1" in
    --ref) shift; REF="${1:?--ref necesita una revisión}" ;;
    --source) shift; SOURCE_DIR="${1:?--source necesita una ruta}" ;;
    --snapshot) MODE=snapshot ;;
    --rollback) MODE=rollback; shift; ROLLBACK_API="${1:?}"; shift; ROLLBACK_CONSOLE="${1:?}" ;;
    *) echo "Argumento desconocido: $1" >&2; exit 2 ;;
  esac
  shift || true
done

log() { printf '[kaanbal-upgrade] %s\n' "$*"; }
die() { printf '[kaanbal-upgrade] ERROR: %s\n' "$*" >&2; exit 1; }

command -v kubectl >/dev/null || die "kubectl no está en PATH"

# ── Snapshot: el punto de retorno ─────────────────────────────────────────────
snapshot() {
  kubectl get deploy "${COMPONENTS[@]}" -n "$NS" \
    -o jsonpath='{range .items[*]}{.metadata.name}={.spec.template.spec.containers[0].image}{"\n"}{end}'
}

log "Estado actual:"
snapshot | sed 's/^/  /'
[[ "$MODE" == snapshot ]] && exit 0

ORG=$(kubectl get cm -n "$NS" -o jsonpath='{.items[0].metadata.name}' >/dev/null 2>&1; echo "${KAANBAL_ORG:-}")
[[ -n "$ORG" ]] || die "Exporta KAANBAL_ORG con la org de GitHub de esta célula (ej: siboenglishnest)"

TOKEN=$(kubectl get secret kaanbal-build-git -n "$NS" -o jsonpath='{.data.token}' | base64 -d)
[[ -n "$TOKEN" ]] || die "No se pudo leer el Secret kaanbal-build-git"

# ── Rollback: restaurar tags. No reconstruye nada ────────────────────────────
if [[ "$MODE" == rollback ]]; then
  log "Revirtiendo a api=$ROLLBACK_API console=$ROLLBACK_CONSOLE"
  # El rollback es exacto porque las imágenes son inmutables y siguen publicadas.
  kubectl set image deploy/kaanbal-api -n "$NS" \
    "kaanbal-api=$(kubectl get deploy kaanbal-api -n "$NS" -o jsonpath='{.spec.template.spec.containers[0].image}' | cut -d: -f1):$ROLLBACK_API"
  kubectl set image deploy/kaanbal-console -n "$NS" \
    "kaanbal-console=$(kubectl get deploy kaanbal-console -n "$NS" -o jsonpath='{.spec.template.spec.containers[0].image}' | cut -d: -f1):$ROLLBACK_CONSOLE"
  log "Revertido. Ojo: ArgoCD volverá a imponer infra-gitops; revierte también el tag allí."
  exit 0
fi

# ── Preflight: el código nuevo debe importar contra las deps reales ──────────
[[ -d "$SOURCE_DIR/SOFTWARE_FACTORY" ]] || die "No hay checkout del monorepo en $SOURCE_DIR"
log "Actualizando el checkout a $REF"
git -C "$SOURCE_DIR" fetch --depth 50 origin "$REF" >/dev/null 2>&1
git -C "$SOURCE_DIR" checkout --quiet --detach FETCH_HEAD
UPSTREAM=$(git -C "$SOURCE_DIR" rev-parse HEAD)
log "Monorepo en ${UPSTREAM:0:7}"

POD=$(kubectl get pod -n "$NS" -l app=kaanbal-api -o jsonpath='{.items[0].metadata.name}')
log "Preflight de imports dentro de $POD"
kubectl cp "$SOURCE_DIR/SOFTWARE_FACTORY/kaanbal-api/app" "$NS/$POD:/tmp/pf-app" >/dev/null
kubectl cp "$SOURCE_DIR/SOFTWARE_FACTORY/kaanbal-api/main.py" "$NS/$POD:/tmp/pf-main.py" >/dev/null
kubectl exec -n "$NS" "$POD" -- sh -c '
  set -e; rm -rf /tmp/pf; mkdir -p /tmp/pf
  mv /tmp/pf-app /tmp/pf/app; cp /tmp/pf-main.py /tmp/pf/main.py
  cd /tmp/pf && python -c "
import importlib, sys
sys.path.insert(0, \"/tmp/pf\")
for m in [\"app.routers.core\",\"app.routers.apps\",\"app.routers.domains\",\"app.services.app_deployer\",\"main\"]:
    importlib.import_module(m)
print(\"preflight ok\")
"
  rm -rf /tmp/pf /tmp/pf-main.py
' || die "El código nuevo no importa contra las dependencias reales. No se despliega nada."

# ── Deriva: nunca pisar código local en silencio ─────────────────────────────
for c in "${COMPONENTS[@]}"; do
  count=$(curl -sf -H "Authorization: Bearer $TOKEN" \
    "https://api.github.com/repos/$ORG/$c/commits?per_page=100" | grep -c '"sha"' || echo 0)
  if [[ "$count" -gt 3 ]]; then
    die "$ORG/$c tiene historia propia ($count commits): puede estar tuneado.
     Resuelve la deriva antes de sobrescribirlo (ver ADR-002)."
  fi
done

# ── Sync: publicar el código nuevo en los repos standalone ───────────────────
for c in "${COMPONENTS[@]}"; do
  W=$(mktemp -d); trap 'rm -rf "$W"' EXIT
  git clone --quiet "https://x-access-token:$TOKEN@github.com/$ORG/$c.git" "$W/repo"
  find "$W/repo" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
  ( cd "$SOURCE_DIR/SOFTWARE_FACTORY/$c" \
    && tar --exclude=.git --exclude=node_modules --exclude=dist \
           --exclude=__pycache__ --exclude='*.pyc' -cf - . ) \
  | ( cd "$W/repo" && tar -xf - )
  cd "$W/repo"
  git config user.email "kaanbal@localhost"
  git config user.name "Kaanbal Upgrade"
  git add -A
  if git diff --cached --quiet; then
    log "$c: sin cambios"
  else
    git commit --quiet -m "upgrade: sync desde software-factory@${UPSTREAM:0:7}"
    git push --quiet origin HEAD:main
    log "$c publicado en ${ORG}/${c} → $(git rev-parse HEAD | cut -c1-7)"
  fi
  cd /; rm -rf "$W"; trap - EXIT
done

log "Código publicado. Falta construir las imágenes y promover los tags en infra-gitops."
log "Snapshot para rollback:"
snapshot | sed 's/^/  /'
