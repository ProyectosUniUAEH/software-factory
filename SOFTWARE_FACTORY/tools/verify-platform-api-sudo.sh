#!/usr/bin/env bash
# Verifica ArgoCD + Vault vía API usando credenciales de /etc/kaanbal/installer.env
set -euo pipefail
TOOLS="$(cd "$(dirname "$0")" && pwd)"
VERIFY_PY="${VERIFY_PY:-$TOOLS/verify-platform-api.py}"
if [ ! -f "$VERIFY_PY" ] && [ -f /tmp/verify-platform-api.py ]; then
  VERIFY_PY=/tmp/verify-platform-api.py
fi
tr -d '\r' < /etc/kaanbal/installer.env > /tmp/kb-installer.env
set -a
# shellcheck disable=SC1091
source /tmp/kb-installer.env
set +a
export KAANBAL_USER="${KAANBAL_ADMIN_USER:-andresbc}"
export KAANBAL_PASS="${KAANBAL_ADMIN_PASS:?missing KAANBAL_ADMIN_PASS}"
exec python3 "$VERIFY_PY"
