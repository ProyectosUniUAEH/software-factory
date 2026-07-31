#!/bin/bash
# Sync inventory/probes/switch/UI to lab tree and rebuild api+console.
set -euo pipefail
ROOT="${KAANBAL_ROOT:-/home/andres/kaanbal-next}"
cd "$ROOT"

# Expect files already scp'd into place; stamp + rebuild
echo "# inventory $(date -u +%Y%m%dT%H%M%SZ)" >> kaanbal-api/app/services/exposure/.rebuild_stamp
sed -i 's/\r$//' kaanbal-api/app/services/exposure/*.py \
  kaanbal-api/app/routers/apps.py \
  kaanbal-api/tests/test_connection_inventory.py \
  kaanbal-console/src/components/ExposureManagerModal.vue \
  kaanbal-console/src/services/appsApi.js 2>/dev/null || true

grep -n 'connection_inventory\|wait_projection\|exposure/status' \
  kaanbal-api/app/services/exposure/switch_service.py \
  kaanbal-api/app/routers/apps.py | head -20

nohup sudo -n env KAANBAL_ROOT="$ROOT" bash /tmp/run-rebuild.sh api \
  > "$ROOT/logs/rebuild-api-inventory.log" 2>&1 &
echo "API_REBUILD_PID=$!"
nohup sudo -n env KAANBAL_ROOT="$ROOT" bash /tmp/run-rebuild.sh console \
  > "$ROOT/logs/rebuild-console-inventory.log" 2>&1 &
echo "CONSOLE_REBUILD_PID=$!"
sleep 4
head -12 "$ROOT/logs/rebuild-api-inventory.log" || true
echo ---
head -12 "$ROOT/logs/rebuild-console-inventory.log" || true
