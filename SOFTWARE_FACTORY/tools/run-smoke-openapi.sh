#!/usr/bin/env bash
set -euo pipefail
POD=$(sudo -n kubectl -n prod get pod -l app=kaanbal-api -o jsonpath='{.items[0].metadata.name}')
echo "POD=$POD"
sudo -n kubectl -n prod cp /tmp/smoke_openapi_exposure.py "$POD:/tmp/smoke_openapi_exposure.py"
sudo -n kubectl -n prod exec "$POD" -- python /tmp/smoke_openapi_exposure.py
echo "---BUILD---"
grep -E 'REBUILD_OK|DONE mode=api|publicado|ERROR' /home/andres/kaanbal-next/logs/rebuild-api-fase5.log | tail -10 || true
pgrep -af 'kaniko.*kaanbal-api' | head -2 || echo kaniko_done
