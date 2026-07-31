#!/usr/bin/env python3
"""Borra devices Tailscale duplicados (mismo hostname) dejando el más reciente / online."""
from __future__ import annotations

import base64
import json
import sys
import urllib.parse
import urllib.request


def parse_env(path):
    cfg = {}
    for raw in open(path, encoding="utf-8"):
        line = raw.strip().replace("\r", "")
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        cfg[k.strip().upper()] = v.strip().strip("'\"")
    return cfg


def main():
    cfg = parse_env(sys.argv[1] if len(sys.argv) > 1 else "/etc/kaanbal/installer.env")
    cid, secret = cfg["TAILSCALE_CLIENT_ID"], cfg["TAILSCALE_CLIENT_SECRET"]
    basic = base64.b64encode(f"{cid}:{secret}".encode()).decode()
    req = urllib.request.Request(
        "https://api.tailscale.com/api/v2/oauth/token",
        data=urllib.parse.urlencode({"grant_type": "client_credentials"}).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded", "Authorization": f"Basic {basic}"},
    )
    token = json.loads(urllib.request.urlopen(req, timeout=30).read())["access_token"]
    req = urllib.request.Request(
        "https://api.tailscale.com/api/v2/tailnet/-/devices",
        headers={"Authorization": f"Bearer {token}"},
    )
    devices = json.loads(urllib.request.urlopen(req, timeout=30).read()).get("devices", [])

    # group by short hostname among tagged lab devices
    groups = {}
    for d in devices:
        tags = d.get("tags") or []
        if not any(str(t).startswith("tag:k8s") or t in ("tag:database", "tag:iot") for t in tags):
            continue
        short = (d.get("hostname") or d.get("name") or "").split(".")[0].lower()
        groups.setdefault(short, []).append(d)

    to_delete = []
    for short, items in groups.items():
        if len(items) < 2 and not short.startswith("tailscale-operator"):
            continue
        # prefer online=True, then highest lastSeen
        def score(d):
            online = 1 if d.get("online") else 0
            last = d.get("lastSeen") or ""
            return (online, last)

        items_sorted = sorted(items, key=score, reverse=True)
        # special: keep only one operator — prefer name ending -1 or highest score
        if short.startswith("tailscale-operator") or all(
            (x.get("hostname") or "").startswith("tailscale-operator") for x in items
        ):
            # regroup all operators together
            pass
        keep, *dupes = items_sorted
        print("KEEP", keep.get("hostname"), keep.get("id"), "online="+str(keep.get("online")))
        for d in dupes:
            to_delete.append(d)
            print("DUP", d.get("hostname"), d.get("id"), "online="+str(d.get("online")))

    # Also: if both tailscale-operator and tailscale-operator-1 exist, drop offline ones
    ops = [d for d in devices if (d.get("hostname") or "").startswith("tailscale-operator")]
    if len(ops) > 1:
        ops_sorted = sorted(ops, key=lambda d: (1 if d.get("online") else 0, d.get("lastSeen") or ""), reverse=True)
        for d in ops_sorted[1:]:
            if d not in to_delete:
                to_delete.append(d)
                print("DUP_OP", d.get("hostname"), d.get("id"))

    apply = "--apply" in sys.argv
    print(f"to_delete={len(to_delete)} mode={'APPLY' if apply else 'DRY'}")
    if not apply:
        return 0
    for d in to_delete:
        did = d.get("id")
        req = urllib.request.Request(
            f"https://api.tailscale.com/api/v2/device/{urllib.parse.quote(did)}",
            headers={"Authorization": f"Bearer {token}"},
            method="DELETE",
        )
        try:
            urllib.request.urlopen(req, timeout=30).read()
            print("DELETED", d.get("hostname"))
        except Exception as e:
            print("FAIL", d.get("hostname"), e)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
