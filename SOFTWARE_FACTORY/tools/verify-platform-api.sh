#!/usr/bin/env bash
# Verifica ArgoCD y Vault vía API pública (requiere credenciales en env).
set -euo pipefail
API="${API_URL:-https://kaanbal-api.softwarefactory.site}"
USER="${KAANBAL_USER:-andresbc}"
PASS="${KAANBAL_PASS:?Set KAANBAL_PASS}"

TOKEN=$(curl -sS -X POST "$API/api/v1/auth/token" \
  --data-urlencode "username=$USER" \
  --data-urlencode "password=$PASS" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo "=== ArgoCD ==="
curl -sS -H "Authorization: Bearer $TOKEN" "$API/api/v1/apps/argocd/all" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('connected:', d.get('connected')); print('count:', d.get('count')); print('reason:', d.get('connection_reason',''))"

echo "=== Vault ==="
curl -sS -H "Authorization: Bearer $TOKEN" "$API/api/v1/system/vault/status" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('configured:', d.get('configured')); print('sealed:', d.get('sealed')); print('reachable:', d.get('reachable'))"
