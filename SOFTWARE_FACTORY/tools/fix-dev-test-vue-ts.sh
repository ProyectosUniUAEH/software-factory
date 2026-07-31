#!/usr/bin/env bash
# Diagnose + restart Tailscale path for dev-test-vue; list orphan candidates.
set -euo pipefail

echo "=== TS NS ==="
sudo -n k3s kubectl -n tailscale get pods,svc -o wide

echo "=== DEV SVC ==="
sudo -n k3s kubectl -n dev get svc,ingress,pods -o wide 2>/dev/null || echo "no_dev_ns_or_empty"
sudo -n k3s kubectl get svc -A | grep -i test-vue || true

echo "=== PROXY LOGS (last 40) ==="
POD=$(sudo -n k3s kubectl -n tailscale get pods -o name | grep test-vue | head -1 || true)
if [[ -n "${POD}" ]]; then
  echo "pod=$POD"
  sudo -n k3s kubectl -n tailscale logs "$POD" -c tailscale --tail=40 2>&1 || true
  echo "=== STATUS INSIDE PROXY ==="
  sudo -n k3s kubectl -n tailscale exec "$POD" -c tailscale -- tailscale status 2>&1 | head -25 || true
else
  echo "NO_TEST_VUE_PROXY"
fi

echo "=== OPERATOR ==="
sudo -n k3s kubectl -n tailscale rollout restart deploy/operator
sudo -n k3s kubectl -n tailscale rollout status deploy/operator --timeout=120s

# Recreate proxy statefulset for test-vue if present
STS=$(sudo -n k3s kubectl -n tailscale get sts -o name 2>/dev/null | grep test-vue | head -1 || true)
if [[ -n "${STS}" ]]; then
  echo "Restarting $STS"
  sudo -n k3s kubectl -n tailscale delete "$STS" --wait=false 2>/dev/null || true
  # operator will recreate; also bounce the annotated service
fi

# Touch service annotations to force reconcile
for ns in dev staging prod; do
  for svc in $(sudo -n k3s kubectl -n "$ns" get svc -o name 2>/dev/null | grep -i test-vue || true); do
    echo "Annotate bounce $ns/$svc"
    sudo -n k3s kubectl -n "$ns" annotate "$svc" kaanbal.io/ts-bounce="$(date +%s)" --overwrite 2>/dev/null || true
  done
done

sleep 15
echo "=== AFTER ==="
sudo -n k3s kubectl -n tailscale get pods -o wide
POD2=$(sudo -n k3s kubectl -n tailscale get pods -o name | grep test-vue | head -1 || true)
if [[ -n "${POD2}" ]]; then
  sudo -n k3s kubectl -n tailscale exec "$POD2" -c tailscale -- tailscale status 2>&1 | head -20 || true
  # try curl via cluster to the ClusterIP of the app
  sudo -n k3s kubectl -n dev get endpoints -l app=test-vue 2>/dev/null || true
fi
echo "DONE_RESTART"
