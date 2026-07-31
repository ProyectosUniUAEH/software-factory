#!/usr/bin/env bash
set -uo pipefail
K="sudo -n k3s kubectl"

echo "=== VAULT: política de sync ==="
$K -n argocd get app vault -o jsonpath='{.spec.syncPolicy}' 2>/dev/null; echo
echo
echo "=== VAULT: condiciones y operación ==="
$K -n argocd get app vault -o jsonpath='{.status.conditions}' 2>/dev/null; echo
echo
$K -n argocd get app vault -o jsonpath='{.status.operationState.phase}{" "}{.status.operationState.message}' 2>/dev/null; echo
echo
echo "=== VAULT: recursos fuera de sync ==="
$K -n argocd get app vault -o json 2>/dev/null \
  | python3 -c '
import sys, json
d = json.load(sys.stdin)
for r in (d.get("status", {}).get("resources") or []):
    if r.get("status") != "Synced" or r.get("health", {}).get("status") not in (None, "Healthy"):
        print("  %-12s %-16s %-10s %s" % (r.get("kind"), r.get("name"),
              r.get("status"), (r.get("health") or {}).get("status", "")))'
echo
echo "=== ¿El repo publicado todavía trae el ingress? ==="
$K -n argocd get app vault -o jsonpath='{.spec.source.path}' 2>/dev/null; echo
