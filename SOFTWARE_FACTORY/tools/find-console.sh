#!/usr/bin/env bash
# Busca en GitHub cualquier repo que pueda contener la consola de despliegue.
set -uo pipefail
CLEAN="$(mktemp)"; trap 'rm -f "$CLEAN"' EXIT
sudo -n cat /etc/kaanbal/installer.env | tr -d '\r' >"$CLEAN"
# shellcheck disable=SC1090
set -a; . "$CLEAN"; set +a
TOKEN="${GITOPS_TOKEN:-${github_token:-}}"

api() { curl -sS -H "Authorization: Bearer $TOKEN" -H 'Accept: application/vnd.github+json' "$@"; }

echo "=== Organizaciones accesibles ==="
api https://api.github.com/user/orgs | python3 -c '
import sys, json
d = json.load(sys.stdin)
if isinstance(d, dict):
    print("  ", d.get("message")); raise SystemExit
for o in d:
    print("  ", o["login"])'

echo
echo "=== Repos que contengan 'console' o 'kaanbal' ==="
api "https://api.github.com/search/repositories?q=kaanbal+in:name&per_page=50" \
  | python3 -c '
import sys, json
d = json.load(sys.stdin)
for r in d.get("items", []):
    print("  %-55s pushed=%s private=%s" % (r["full_name"], r["pushed_at"][:10], r["private"]))'

echo
echo "=== Todos mis repos (los 100 mas recientes) ==="
api "https://api.github.com/user/repos?per_page=100&sort=pushed" \
  | python3 -c '
import sys, json
d = json.load(sys.stdin)
if isinstance(d, dict):
    print("  ", d.get("message")); raise SystemExit
for r in d:
    print("  %-58s pushed=%s" % (r["full_name"], r["pushed_at"][:10]))'
