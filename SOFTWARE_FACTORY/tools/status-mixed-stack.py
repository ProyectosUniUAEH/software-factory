#!/usr/bin/env python3
import json
import subprocess
from pathlib import Path


def sh(c):
    r = subprocess.run(c, shell=True, text=True, capture_output=True)
    print(((r.stdout or "") + (r.stderr or "")).strip())


print("=== n8n pods ===")
sh("k3s kubectl get pods -A | grep n8n || true")
sh("k3s kubectl -n prod logs lab-n8n-0 --tail=25 2>&1 || true")
print("\n=== react ===")
sh("k3s kubectl -n argocd get applications | grep react || true")
sh("k3s kubectl get pods -A | grep react || true")

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
    if a.get("name") in ("lab-react", "lab-n8n", "lab-emqx", "lab-api", "lab-mongo", "lab-pg"):
        print(a.get("name"), a.get("status"), (a.get("error") or "")[:220])

print("\n=== curls ===")
for u in (
    "https://lab-n8n.softwarefactory.site/",
    "https://lab-emqx.softwarefactory.site/",
    "https://lab-react.softwarefactory.site/",
    "https://lab-api.softwarefactory.site/health",
    "https://lab-pg.softwarefactory.site/",
):
    sh(f"curl -sS -o /dev/null -w '{u} -> %{{http_code}}\\n' --max-time 12 '{u}'")

print("\n=== exposure summary argo ===")
sh(
    "k3s kubectl -n argocd get applications "
    "-o custom-columns=NAME:.metadata.name,SYNC:.status.sync.status,HEALTH:.status.health.status "
    "--no-headers | grep lab-"
)
print("STATUS_DONE")
