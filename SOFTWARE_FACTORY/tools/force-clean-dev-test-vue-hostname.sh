#!/usr/bin/env bash
# Force clean hostname dev-test-vue (delete -1 and offline twin, re-register once)
set -euo pipefail
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
for d in devs:
    host=(d.get("hostname") or d.get("name") or "")
    short=host.split(".")[0].lower()
    if short.startswith("dev-test-vue"):
        did=d["id"]
        print("DELETE", host, did)
        r=urllib.request.Request(f"https://api.tailscale.com/api/v2/device/{urllib.parse.quote(did)}",
            headers={"Authorization":f"Bearer {tok}"}, method="DELETE")
        try:
            urllib.request.urlopen(r,timeout=30).read(); print(" OK")
        except Exception as e:
            print(" FAIL", e)
PY

for x in $(sudo -n k3s kubectl -n tailscale get sts,secret,pod -o name 2>/dev/null | grep -i test-vue || true); do
  sudo -n k3s kubectl -n tailscale delete "$x" --wait=false || true
done
sleep 5
sudo -n k3s kubectl -n dev annotate svc test-vue-ts kaanbal.io/ts-bounce="$(date +%s)" --overwrite
sudo -n k3s kubectl -n tailscale rollout restart deploy/operator
sudo -n k3s kubectl -n tailscale rollout status deploy/operator --timeout=120s
for i in $(seq 1 30); do
  p=$(sudo -n k3s kubectl -n tailscale get pods --no-headers 2>/dev/null | grep test-vue | grep Running || true)
  [[ -n "$p" ]] && break
  sleep 4
done
sleep 12
POD=$(sudo -n k3s kubectl -n tailscale get pods -o name | grep test-vue | head -1)
echo "POD=$POD"
sudo -n k3s kubectl -n tailscale exec "$POD" -c tailscale -- tailscale status 2>&1 | head -12
sudo -n k3s kubectl -n tailscale logs "$POD" -c tailscale --tail=40 2>&1 | grep -i 'active login' | tail -3
echo "CLEAN_HOSTNAME_DONE"
