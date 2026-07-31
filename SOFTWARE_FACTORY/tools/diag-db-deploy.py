#!/usr/bin/env python3
import subprocess
import json
from pathlib import Path


def sh(cmd):
    r = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    out = ((r.stdout or "") + (r.stderr or "")).strip()
    print(out)
    return out


print("=== argo apps lab ===")
sh("k3s kubectl -n argocd get applications -o name | grep -i lab || true")
sh(
    "k3s kubectl -n argocd get applications "
    "-o custom-columns=NAME:.metadata.name,SYNC:.status.sync.status,HEALTH:.status.health.status,PATH:.spec.source.path "
    "--no-headers | grep -iE 'lab|mongo|pg' || true"
)

print("\n=== pods all envs ===")
for ns in ("dev", "staging", "prod"):
    print(f"-- {ns}")
    sh(f"k3s kubectl -n {ns} get pods,sts,svc --no-headers 2>/dev/null | grep -iE 'lab|mongo|pg' || echo '(none)'")

print("\n=== gitops paths ===")
sh("ls /home/andres/kaanbal-next/infra-gitops/apps/ | grep -i lab || true")
sh("ls /home/andres/kaanbal-next/infra-gitops/apps/lab-mongo/overlays 2>/dev/null || echo no local lab-mongo")

print("\n=== API apps ===")
cfg = {}
for line in Path("/etc/kaanbal/installer.env").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    cfg[k.strip()] = v.strip()
out = subprocess.check_output(
    [
        "curl", "-sS", "-X", "POST",
        "https://kaanbal-api.softwarefactory.site/api/v1/auth/token",
        "--data-urlencode", f"username={cfg['KAANBAL_ADMIN_USER']}",
        "--data-urlencode", f"password={cfg['KAANBAL_ADMIN_PASS']}",
    ],
    text=True,
)
token = json.loads(out)["access_token"]
apps = subprocess.check_output(
    [
        "curl", "-sS", "-H", f"Authorization: Bearer {token}",
        "https://kaanbal-api.softwarefactory.site/api/v1/apps",
    ],
    text=True,
)
print(apps[:2000])

print("\n=== status full lab-mongo ===")
st = subprocess.check_output(
    [
        "curl", "-sS", "-H", f"Authorization: Bearer {token}",
        "https://kaanbal-api.softwarefactory.site/api/v1/apps/lab-mongo/status/full",
    ],
    text=True,
)
print(st[:2500])

print("\n=== events prod ===")
sh("k3s kubectl -n prod get events --sort-by=.lastTimestamp 2>/dev/null | tail -25")
print("DIAG_DB_DONE")
