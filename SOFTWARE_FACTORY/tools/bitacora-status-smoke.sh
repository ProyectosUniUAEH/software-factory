#!/usr/bin/env bash
set -euo pipefail
echo "=== PUBLIC CORE ==="
curl -sS -o /dev/null -w "console:%{http_code}\n" --max-time 12 https://kaanbal-console.softwarefactory.site/ || true
curl -sS -o /dev/null -w "api:%{http_code}\n" --max-time 12 https://kaanbal-api.softwarefactory.site/health || true
echo "=== INGRESS APPS ==="
sudo -n k3s kubectl get ingress -A --no-headers 2>/dev/null | awk '{print $1,$2,$3}' || true
echo "=== TS SERVICES ==="
sudo -n k3s kubectl get svc -A -o jsonpath='{range .items[*]}{.metadata.namespace}{" "}{.metadata.name}{" "}{.metadata.annotations.tailscale\.com/hostname}{"\n"}{end}' 2>/dev/null | grep -v ' $' || true
echo "=== TS PODS ==="
sudo -n k3s kubectl -n tailscale get pods --no-headers 2>/dev/null || true
echo "=== TS DEVICES kaanbal/lab/test ==="
cd /home/andres/kaanbal-next 2>/dev/null || true
sudo -n python3 - <<'PY'
import json, urllib.parse, urllib.request, base64
cfg={}
for line in open("/etc/kaanbal/installer.env"):
    line=line.strip().replace("\r","")
    if not line or line.startswith("#") or "=" not in line: continue
    k,v=line.split("=",1); cfg[k.strip().upper()]=v.strip()
cid=cfg.get("TAILSCALE_CLIENT_ID",""); sec=cfg.get("TAILSCALE_CLIENT_SECRET","")
if not cid:
    print("NO_TS_CREDS"); raise SystemExit(0)
req=urllib.request.Request("https://api.tailscale.com/api/v2/oauth/token",
    data=urllib.parse.urlencode({"grant_type":"client_credentials"}).encode(),
    headers={"Content-Type":"application/x-www-form-urlencoded",
             "Authorization":"Basic "+base64.b64encode(f"{cid}:{sec}".encode()).decode()})
tok=json.loads(urllib.request.urlopen(req,timeout=30).read())["access_token"]
req=urllib.request.Request("https://api.tailscale.com/api/v2/tailnet/-/devices",
    headers={"Authorization":f"Bearer {tok}"})
devs=json.loads(urllib.request.urlopen(req,timeout=30).read()).get("devices",[])
for d in sorted(devs, key=lambda x: x.get("name") or ""):
    name=d.get("name") or ""
    if any(x in name.lower() for x in ("kaanbal","lab","test","vue","n8n","react","api")):
        print(name, "online="+str(d.get("online")), "tags="+str(d.get("tags")))
PY
echo "SMOKE_OK"
