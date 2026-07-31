#!/usr/bin/env bash
# Reinstalación completa desatendida con log timestamped en segundo plano.
# Uso: nohup sudo bash tools/reinstall-unattended.sh /path/to/.env >> logs/reinstall.log 2>&1 &
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${1:?usage: reinstall-unattended.sh /path/to/.env}"
LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"
STAMP="$(date +%Y%m%d-%H%M%S)"
LOG="$LOG_DIR/reinstall-$STAMP.log"
exec > >(tee -a "$LOG") 2>&1

log() { echo "[$(date -Iseconds)] $*"; }

log "=== reinstall-unattended inicio ==="
log "ROOT=$ROOT ENV=$ENV_FILE"

if [ ! -f "$ENV_FILE" ]; then
  log "ERROR: no existe $ENV_FILE"
  exit 1
fi

log "--- preflight ---"
sudo bash "$ROOT/install.sh" --check --env "$ENV_FILE" || exit 1

log "--- install: reset-local + reset-remote + unattended ---"
cd "$ROOT"
sudo bash ./install.sh \
  --reset-local \
  --reset-remote \
  --preserve-credentials \
  --unattended \
  --env "$ENV_FILE"

log "--- post-install verify ---"
if [ -x "$ROOT/tools/verify-platform-api-sudo.sh" ]; then
  bash "$ROOT/tools/verify-platform-api-sudo.sh" && log "verify-platform-api OK" || log "verify-platform-api FALLÓ"
fi
if [ -x "$ROOT/tools/smoke-login.sh" ]; then
  bash "$ROOT/tools/smoke-login.sh" /etc/kaanbal/installer.env && log "smoke-login OK" || log "smoke-login FALLÓ"
fi
if [ -x "$ROOT/tools/publish-templates-sudo.sh" ]; then
  bash "$ROOT/tools/publish-templates-sudo.sh" && log "publish-templates OK" || log "publish-templates FALLÓ"
fi

log "=== reinstall-unattended fin ==="
log "Log: $LOG"
