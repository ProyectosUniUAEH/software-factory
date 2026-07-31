#!/usr/bin/env python3
import json
import subprocess
from pathlib import Path


def sh(cmd):
    r = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    print(((r.stdout or "") + (r.stderr or "")).strip())


print("=== n8n logs prod ===")
sh("k3s kubectl -n prod logs lab-n8n-0 --tail=40 2>&1 || true")
print("\n=== n8n logs dev ===")
sh("k3s kubectl -n dev logs lab-n8n-0 --tail=40 2>&1 || true")
print("\n=== n8n describe prod ===")
sh("k3s kubectl -n prod describe pod lab-n8n-0 2>&1 | tail -35")
print("\n=== n8n env sample ===")
sh("k3s kubectl -n prod get pod lab-n8n-0 -o jsonpath='{.spec.containers[0].env}' 2>&1 | python3 -c 'import sys,json; d=json.load(sys.stdin); print(\"\\n\".join(f\"{e.get(\\\"name\\\")}={e.get(\\\"value\\\") or e.get(\\\"valueFrom\\\")}\" for e in d))' 2>&1 | head -40")

print("\n=== lab-react API error full ===")
cfg = {}
for line in Path("/etc/kaanbal/installer.env").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    cfg[k.strip()] = v.strip()
tok = json.loads(
    subprocess.check_output(
        [
            "curl", "-sS", "-X", "POST",
            "https://kaanbal-api.softwarefactory.site/api/v1/auth/token",
            "--data-urlencode", f"username={cfg['KAANBAL_ADMIN_USER']}",
            "--data-urlencode", f"password={cfg['KAANBAL_ADMIN_PASS']}",
        ],
        text=True,
    )
)["access_token"]
apps = json.loads(
    subprocess.check_output(
        [
            "curl", "-sS", "-H", f"Authorization: Bearer {tok}",
            "https://kaanbal-api.softwarefactory.site/api/v1/apps",
        ],
        text=True,
    )
)
for a in apps:
    if a.get("name") == "lab-react":
        print(a.get("error"))

print("\n=== public checks ===")
for url in (
    "https://lab-pg.softwarefactory.site/",
    "https://lab-mongo.softwarefactory.site/",
    "https://lab-api.softwarefactory.site/health",
    "https://lab-api.softwarefactory.site/docs",
    "https://lab-emqx.softwarefactory.site/",
    "https://lab-n8n.softwarefactory.site/",
):
    sh(f"curl -sS -o /dev/null -w '{url} -> %{{http_code}}\\n' --max-time 12 '{url}' || echo fail")

print("\n=== bindings on lab-api ===")
sh("k3s kubectl -n prod exec deploy/lab-api -- env 2>/dev/null | grep -E 'DB_|MONGO_|POSTGRES' | head -30")
print("DONE")
