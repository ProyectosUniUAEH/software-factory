#!/usr/bin/env python3
import subprocess


def sh(cmd):
    r = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    print(((r.stdout or "") + (r.stderr or "")).strip())


print("=== HTTP ===")
for u in (
    "https://lab-n8n.softwarefactory.site/",
    "https://lab-emqx.softwarefactory.site/",
    "https://lab-react.softwarefactory.site/",
    "https://lab-api.softwarefactory.site/health",
    "https://lab-pg.softwarefactory.site/",
    "https://lab-mongo.softwarefactory.site/",
):
    sh(f"curl -sS -o /dev/null -w '{u} -> %{{http_code}}\\n' --max-time 12 '{u}'")

print("\n=== bindings ===")
sh("k3s kubectl -n prod exec deploy/lab-api -- env | grep -E 'DB_HOST|MONGO_HOST|DB_URI|MONGO_URI' | sed -E 's#://[^:]+:[^@]+@#://***:***@#g'")

print("\n=== n8n local ===")
sh("k3s kubectl -n prod get pod lab-n8n-0")
sh("k3s kubectl -n prod logs lab-n8n-0 --tail=8")

print("\n=== argo lab ===")
sh(
    "k3s kubectl -n argocd get applications "
    "-o custom-columns=NAME:.metadata.name,SYNC:.status.sync.status,HEALTH:.status.health.status "
    "--no-headers | grep lab-"
)
print("FINAL")
