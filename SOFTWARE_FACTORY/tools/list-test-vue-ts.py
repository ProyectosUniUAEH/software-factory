#!/usr/bin/env python3
"""List Tailscale devices matching test-vue (no secrets printed)."""
import json, os, sys, urllib.request, urllib.parse

def load_env(path="/etc/kaanbal/installer.env"):
    out = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out

env = load_env()
cid = env.get("TAILSCALE_CLIENT_ID") or env.get("tailscale_client_id")
csec = env.get("TAILSCALE_CLIENT_SECRET") or env.get("tailscale_client_secret")
if not cid or not csec:
    print("NO_TS_OAUTH"); sys.exit(1)

data = urllib.parse.urlencode({"client_id": cid, "client_secret": csec}).encode()
req = urllib.request.Request(
    "https://api.tailscale.com/api/v2/oauth/token",
    data=data,
    method="POST",
    headers={"Content-Type": "application/x-www-form-urlencoded"},
)
tok = json.load(urllib.request.urlopen(req, timeout=30))["access_token"]
req2 = urllib.request.Request(
    "https://api.tailscale.com/api/v2/tailnet/-/devices",
    headers={"Authorization": f"Bearer {tok}"},
)
devices = json.load(urllib.request.urlopen(req2, timeout=30)).get("devices") or []
print(f"DEVICES_TOTAL={len(devices)}")
for d in devices:
    name = (d.get("name") or d.get("hostname") or "")
    if "test-vue" in name.lower() or "test-vue" in (d.get("hostname") or "").lower():
        print(
            f"{name}\thostname={d.get('hostname')}\tonline={d.get('online')}\t"
            f"addresses={d.get('addresses')}\tlastSeen={d.get('lastSeen')}"
        )
