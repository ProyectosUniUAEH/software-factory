#!/usr/bin/env bash
# Fix MagicDNS for test-vue dev: bounce proxy state + operator, then cleanup orphans.
set -euo pipefail

echo "=== 1) Cluster desired TS hostnames ==="
sudo -n k3s kubectl get svc,ingress -A -o json 2>/dev/null | python3 -c '
import json,sys
d=json.load(sys.stdin)
for i in d.get("items",[]):
  a=(i.get("metadata") or {}).get("annotations") or {}
  h=a.get("tailscale.com/hostname")
  if h: print(i["kind"], i["metadata"]["namespace"]+"/"+i["metadata"]["name"], h)
'

echo "=== 2) Delete proxy state so device re-registers ==="
# StatefulSet + kube state secret used by tailscaled
for x in $(sudo -n k3s kubectl -n tailscale get sts -o name 2>/dev/null | grep -i test-vue || true); do
  echo "delete $x"; sudo -n k3s kubectl -n tailscale delete "$x" --wait=false || true
done
for x in $(sudo -n k3s kubectl -n tailscale get secret -o name 2>/dev/null | grep -i test-vue || true); do
  echo "delete $x"; sudo -n k3s kubectl -n tailscale delete "$x" --wait=false || true
done
for x in $(sudo -n k3s kubectl -n tailscale get pods -o name 2>/dev/null | grep -i test-vue || true); do
  echo "delete $x"; sudo -n k3s kubectl -n tailscale delete "$x" --wait=false || true
done

echo "=== 3) Bounce annotated Service in all ns ==="
for ns in dev staging prod; do
  for svc in $(sudo -n k3s kubectl -n "$ns" get svc -o name 2>/dev/null | grep -iE 'test-vue' || true); do
    echo "bounce $ns/$svc"
    sudo -n k3s kubectl -n "$ns" annotate "$svc" kaanbal.io/ts-bounce="$(date +%s)" --overwrite || true
  done
done

echo "=== 4) Restart operator ==="
sudo -n k3s kubectl -n tailscale rollout restart deploy/operator
sudo -n k3s kubectl -n tailscale rollout status deploy/operator --timeout=180s

echo "=== 5) Wait for new proxy ==="
for i in $(seq 1 36); do
  p=$(sudo -n k3s kubectl -n tailscale get pods --no-headers 2>/dev/null | grep -i test-vue | grep Running || true)
  if [[ -n "$p" ]]; then echo "proxy_up: $p"; break; fi
  sleep 5
done

POD=$(sudo -n k3s kubectl -n tailscale get pods -o name 2>/dev/null | grep -i test-vue | head -1 || true)
if [[ -n "$POD" ]]; then
  sleep 8
  echo "=== 6) status inside proxy ==="
  sudo -n k3s kubectl -n tailscale exec "$POD" -c tailscale -- tailscale status 2>&1 | head -30 || true
  echo "=== 7) curl backend via cluster ==="
  # discover target svc
  sudo -n k3s kubectl get svc -A | grep -i test-vue || true
fi

echo "=== 8) Cleanup Tailscale orphans (APPLY) ==="
cd /home/andres/kaanbal-next
sudo -n python3 -u tools/cleanup-tailscale-orphans.py --apply --env /etc/kaanbal/installer.env

echo "=== 9) Final pods/devices hint ==="
sudo -n k3s kubectl -n tailscale get pods
sudo -n python3 -u tools/cleanup-tailscale-orphans.py --env /etc/kaanbal/installer.env | tail -40
echo "FIX_DONE"
echo "Prueba: http://dev-test-vue.tail31971f.ts.net/"
