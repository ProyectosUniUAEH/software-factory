#!/usr/bin/env python3
import sys
sys.path.insert(0, "/home/andres/kaanbal-next/installer")
import server

cfg = {}
for line in open("/etc/kaanbal/installer.env"):
    line = line.strip().replace("\r", "")
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        cfg[k] = v

ok, why = server.tailscale_can_tag(cfg["TAILSCALE_CLIENT_ID"], cfg["TAILSCALE_CLIENT_SECRET"])
print("can_tag_k8s_operator:", ok)
print("reason:", why or "OK")
