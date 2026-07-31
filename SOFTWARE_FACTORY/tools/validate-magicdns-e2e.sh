#!/usr/bin/env bash
# Validate MagicDNS path for dev-test-vue from the Ubuntu lab host.
set -euo pipefail
echo "=== 1) Cluster Service + Endpoints ==="
sudo -n k3s kubectl -n dev get svc test-vue test-vue-ts -o wide 2>&1
sudo -n k3s kubectl -n dev get endpoints test-vue test-vue-ts -o wide 2>&1
sudo -n k3s kubectl -n dev get pods -l app=test-vue -o wide 2>&1 || sudo -n k3s kubectl -n dev get pods -o wide 2>&1 | head -20

echo "=== 2) Curl ClusterIP ==="
IP=$(sudo -n k3s kubectl -n dev get svc test-vue -o jsonpath='{.spec.clusterIP}' 2>/dev/null || true)
echo "clusterIP=$IP"
if [[ -n "$IP" ]]; then
  curl -sS -o /dev/null -w "clusterIP:%{http_code}\n" --max-time 5 "http://$IP/" || echo "clusterIP:FAIL"
fi

echo "=== 3) Tailscale proxy pod ==="
sudo -n k3s kubectl -n tailscale get pods -o wide | grep -E 'test-vue|NAME' || true
POD=$(sudo -n k3s kubectl -n tailscale get pods -o name | grep test-vue | head -1 || true)
echo "POD=$POD"
if [[ -n "$POD" ]]; then
  sudo -n k3s kubectl -n tailscale exec "$POD" -c tailscale -- tailscale status 2>&1 | head -20
  sudo -n k3s kubectl -n tailscale exec "$POD" -c tailscale -- tailscale ip -4 2>&1 || true
  # From inside proxy, can it reach the backend?
  BACKEND=$(sudo -n k3s kubectl -n dev get svc test-vue -o jsonpath='{.spec.clusterIP}')
  sudo -n k3s kubectl -n tailscale exec "$POD" -c tailscale -- wget -qO- --timeout=5 "http://$BACKEND/" 2>&1 | head -c 120 || echo "proxy->backend FAIL"
  echo
  # MagicDNS resolve from proxy
  sudo -n k3s kubectl -n tailscale exec "$POD" -c tailscale -- getent hosts dev-test-vue.tail31971f.ts.net 2>&1 || true
fi

echo "=== 4) Tailscale API device ==="
cd /home/andres/kaanbal-next
sudo -n python3 - <<'PY'
import base64, json, urllib.parse, urllib.request
cfg={}
for raw in open("/etc/kaanbal/installer.env"):
    line=raw.strip().replace("\r","")
    if line and not line.startswith("#") and "=" in line:
        k,v=line.split("=",1); cfg[k.strip().upper()]=v.strip()
basic=base64.b64encode(f"{cfg['TAILSCALE_CLIENT_ID']}:{cfg['TAILSCALE_CLIENT_SECRET']}".encode()).decode()
req=urllib.request.Request("https://api.tailscale.com/api/v2/oauth/token",
    data=urllib.parse.urlencode({"grant_type":"client_credentials"}).encode(),
    headers={"Content-Type":"application/x-www-form-urlencoded","Authorization":f"Basic {basic}"})
tok=json.loads(urllib.request.urlopen(req,timeout=30).read())["access_token"]
req=urllib.request.Request("https://api.tailscale.com/api/v2/tailnet/-/devices",
    headers={"Authorization":f"Bearer {tok}"})
devs=json.loads(urllib.request.urlopen(req,timeout=30).read()).get("devices",[])
for d in sorted(devs, key=lambda x: x.get("hostname") or ""):
    host=d.get("hostname") or d.get("name") or ""
    if "test-vue" in host.lower() or "operator" in host.lower() or "vault" in host.lower():
        print({
            "hostname": host,
            "name": d.get("name"),
            "online": d.get("online"),
            "addresses": d.get("addresses"),
            "tags": d.get("tags"),
            "lastSeen": d.get("lastSeen"),
            "os": d.get("os"),
        })
PY

echo "=== 5) Host Ubuntu has tailscale client? ==="
command -v tailscale >/dev/null && sudo -n tailscale status 2>&1 | head -25 || echo "NO_TAILSCALE_ON_UBUNTU_HOST"

echo "LAB_VALIDATE_DONE"
