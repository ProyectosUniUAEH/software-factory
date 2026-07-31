#!/usr/bin/env python3
import json
import subprocess
from pathlib import Path


def sh(cmd):
    r = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    print(((r.stdout or "") + (r.stderr or "")).strip())


print("=== argo lab apps ===")
sh(
    "k3s kubectl -n argocd get applications "
    "-o custom-columns=NAME:.metadata.name,SYNC:.status.sync.status,HEALTH:.status.health.status "
    "--no-headers"
)

print("\n=== pods by ns ===")
for ns in ("dev", "staging", "prod"):
    print(f"-- {ns}")
    sh(f"k3s kubectl -n {ns} get pods --no-headers 2>/dev/null")

print("\n=== labels sample ===")
sh("k3s kubectl -n prod get deploy,sts -o wide --show-labels 2>/dev/null | head -40")

print("\n=== API app statuses ===")
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
    err = (a.get("error") or "")[:180]
    print(f"{a.get('name')}: status={a.get('status')} err={err}")

print("\n=== gitops apps dir (remote via ls local checkout if synced) ===")
sh("ls /home/andres/kaanbal-next/infra-gitops/apps/ | head -40")
# Check GH for lab-mongo path
out = subprocess.check_output(
    [
        "curl", "-sS",
        "-H", f"Authorization: Bearer {cfg['GITOPS_TOKEN']}",
        "-H", "Accept: application/vnd.github+json",
        "-H", "User-Agent: kaanbal",
        "https://api.github.com/repos/ProyectosUniUAEH/infra-gitops/contents/apps",
    ],
    text=True,
)
try:
    items = json.loads(out)
    print("GH apps:", [i.get("name") for i in items if isinstance(i, dict)])
except Exception:
    print(out[:500])
print("DONE")
