#!/usr/bin/env python3
"""Diagnose kaanbal-api after platform restore."""
from pathlib import Path
import subprocess


def sh(cmd: str) -> str:
    r = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    out = ((r.stdout or "") + (r.stderr or "")).strip()
    print(out)
    return out


print("=== ArgoCD apps ===")
sh(
    "k3s kubectl -n argocd get applications "
    "-o custom-columns=NAME:.metadata.name,SYNC:.status.sync.status,HEALTH:.status.health.status "
    "--no-headers"
)

print("\n=== prod pods/svc/ingress ===")
sh("k3s kubectl -n prod get pods,svc,ingress --no-headers")

print("\n=== cloudflared folder ===")
sh("ls -la /home/andres/kaanbal-next/infra-gitops/apps/cloudflared/")

print("\n=== external curls ===")
for path in ("/api/v1/health", "/", "/docs", "/health", "/openapi.json"):
    sh(
        "curl -sS -o /dev/null -w '"
        + path
        + "=%{http_code}\\n' --max-time 10 https://kaanbal-api.softwarefactory.site"
        + path
    )

print("\n=== deploy/ingress detail ===")
sh("k3s kubectl -n prod get deploy kaanbal-api -o wide")
sh("k3s kubectl -n prod get ingress -o wide")

ip = sh("k3s kubectl -n prod get svc kaanbal-api -o jsonpath='{.spec.clusterIP}'")
ip = ip.strip().splitlines()[-1] if ip else ""
print(f"\nclusterIP={ip!r}")
if ip and ip[0].isdigit():
    for path in ("/docs", "/api/v1/health", "/health"):
        sh(
            f"curl -sS -o /dev/null -w 'svc{path}=%{{http_code}}\\n' "
            f"--max-time 5 http://{ip}:8000{path} || true"
        )

print("\n=== auth probe ===")
cfg = {}
for line in Path("/etc/kaanbal/installer.env").read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    cfg[k.strip()] = v.strip()

out = subprocess.check_output(
    [
        "curl",
        "-sS",
        "-w",
        "\nHTTP:%{http_code}",
        "-X",
        "POST",
        "https://kaanbal-api.softwarefactory.site/api/v1/auth/token",
        "--data-urlencode",
        f"username={cfg['KAANBAL_ADMIN_USER']}",
        "--data-urlencode",
        f"password={cfg['KAANBAL_ADMIN_PASS']}",
    ],
    text=True,
)
print(out[:400])
print("DIAG_DONE")
