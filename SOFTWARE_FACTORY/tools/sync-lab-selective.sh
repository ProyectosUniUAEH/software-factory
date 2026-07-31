#!/usr/bin/env bash
# Sync selected trees from this checkout into ~/kaanbal-next on the lab host.
# Run FROM the Windows/dev machine via: bash tools/sync-lab-selective.sh
# Or paste paths into scp from PowerShell (see bottom).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOST="${LAB_SSH:-andres-lan}"
DEST="${LAB_DEST:-kaanbal-next}"

sync_one() {
  local rel="$1"
  echo ">> $rel"
  ssh "$HOST" "mkdir -p ~/${DEST}/$(dirname "$rel")"
  scp -r "$ROOT/$rel" "${HOST}:~/${DEST}/$(dirname "$rel")/"
}

# Core product pieces for Fase 2+3 exposure lifecycle
sync_one "kaanbal-api/app/services/exposure"
sync_one "kaanbal-api/app/services/app_deployer.py"
sync_one "kaanbal-api/app/services/template_spec.py"
sync_one "kaanbal-api/app/routers/apps.py"
sync_one "kaanbal-api/app/models.py"
sync_one "kaanbal-api/app/defaults.py"
sync_one "kaanbal-api/tests"
sync_one "kaanbal-templates/catalog.json"
sync_one "tools/rebuild-platform.sh"
sync_one "docs/EXPOSURE_LIFECYCLE_BITACORA.md"

echo "SYNC_OK → ${HOST}:~/${DEST}"
echo "Next on lab:"
echo "  sudo bash ~/${DEST}/tools/rebuild-platform.sh api"
echo "  sudo bash ~/${DEST}/tools/rebuild-platform.sh templates"
