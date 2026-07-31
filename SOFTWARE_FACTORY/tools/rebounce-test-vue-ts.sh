#!/usr/bin/env bash
set -euo pipefail
# Re-bounce test-vue proxy after duplicate delete, then show status
for x in $(sudo -n k3s kubectl -n tailscale get sts,secret,pod -o name 2>/dev/null | grep -i test-vue || true); do
  sudo -n k3s kubectl -n tailscale delete "$x" --wait=false || true
done
sudo -n k3s kubectl -n dev annotate svc test-vue-ts kaanbal.io/ts-bounce="$(date +%s)" --overwrite || true
sudo -n k3s kubectl -n tailscale rollout restart deploy/operator
sudo -n k3s kubectl -n tailscale rollout status deploy/operator --timeout=120s
for i in $(seq 1 24); do
  p=$(sudo -n k3s kubectl -n tailscale get pods --no-headers 2>/dev/null | grep test-vue | grep Running || true)
  [[ -n "$p" ]] && break
  sleep 5
done
sleep 10
POD=$(sudo -n k3s kubectl -n tailscale get pods -o name | grep test-vue | head -1)
echo "POD=$POD"
sudo -n k3s kubectl -n tailscale exec "$POD" -c tailscale -- tailscale status 2>&1 | head -20
sudo -n k3s kubectl -n tailscale logs "$POD" -c tailscale --tail=50 2>&1 | grep -iE 'active login|authorized|serving|error|NoState|Starting' | tail -25
# curl the backend service from inside cluster
sudo -n k3s kubectl -n dev run curl-tv --rm -i --restart=Never --image=curlimages/curl:8.5.0 -- \
  curl -sS -o /dev/null -w "svc_test_vue:%{http_code}\n" --max-time 8 http://test-vue.dev.svc.cluster.local/ || true
sudo -n k3s kubectl -n dev run curl-tv2 --rm -i --restart=Never --image=curlimages/curl:8.5.0 -- \
  curl -sS -o /dev/null -w "svc_test_vue_ts:%{http_code}\n" --max-time 8 http://test-vue-ts.dev.svc.cluster.local/ || true
echo "VERIFY_DONE"
