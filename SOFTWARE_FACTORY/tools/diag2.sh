#!/usr/bin/env bash
set -uo pipefail
K="sudo -n k3s kubectl"

echo "=== APPLICATION tailscale-operator ==="
$K -n argocd get app tailscale-operator -o jsonpath='{.spec.source.path}{"\n"}{.status.conditions}{"\n"}' 2>&1
echo
echo "=== ¿La genera el ApplicationSet? ==="
$K -n argocd get applicationset kaanbal-engine-apps -o jsonpath='{.spec.generators}{"\n"}' 2>&1
echo
echo "=== VAULT ==="
$K -n vault get pods 2>&1
echo
$K -n vault get events --sort-by=.lastTimestamp 2>&1 | tail -10
echo
echo "=== ¿tailscale-operator sigue en el repo publicado? ==="
ls -la /tmp/kaanbal-gitops/apps/ 2>&1
