#!/usr/bin/env python3
"""Lista devices Tailscale y busca front1."""
import json, urllib.parse, urllib.request

cfg = {}
for line in open("/etc/kaanbal/installer.env"):
    line = line.strip().replace("\r", "")
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        cfg[k] = v

data = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
req = urllib.request.Request(
    "https://api.tailscale.com/api/v2/oauth/token",
    data=data,
    headers={"Content-Type": "application/x-www-form-urlencoded"},
)
import base64
cred = base64.b64encode(f"{cfg['TAILSCALE_CLIENT_ID']}:{cfg['TAILSCALE_CLIENT_SECRET']}".encode()).decode()
req.add_header("Authorization", f"Basic {cred}")
with urllib.request.urlopen(req, timeout=30) as r:
    token = json.loads(r.read().decode())["access_token"]

req = urllib.request.Request(
    "https://api.tailscale.com/api/v2/tailnet/-/devices",
    headers={"Authorization": f"Bearer {token}"},
)
with urllib.request.urlopen(req, timeout=30) as r:
    devices = json.loads(r.read().decode()).get("devices", [])

for d in devices:
    name = d.get("name") or d.get("hostname") or ""
    tags = d.get("tags") or []
    addrs = d.get("addresses") or []
    if "front" in name.lower() or "k8s" in str(tags).lower() or "operator" in name.lower():
        print(f"{name} tags={tags} addrs={addrs} online={d.get('online')}")

print("--- all hostnames ---")
for d in sorted(devices, key=lambda x: x.get("hostname") or ""):
    print(d.get("hostname"), d.get("name"), d.get("online"))
