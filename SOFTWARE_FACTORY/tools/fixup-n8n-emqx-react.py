#!/usr/bin/env python3
"""Fix n8n PVC encryption mismatch + ensure public Ingress for n8n/emqx prod + redeploy react."""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

API = "https://kaanbal-api.softwarefactory.site"


def sh(cmd):
    r = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    out = ((r.stdout or "") + (r.stderr or "")).strip()
    if out:
        print(out)
    return r.returncode, out


def load_env():
    data = {}
    for line in Path("/etc/kaanbal/installer.env").read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        data[k.strip()] = v.strip()
    return data


def curl_json(method, path, token=None, form=None, body=None):
    cmd = ["curl", "-sS", "-w", "\n__HTTP__%{http_code}", "-X", method, f"{API}{path}"]
    if token:
        cmd += ["-H", f"Authorization: Bearer {token}"]
    if form is not None:
        for k, v in form.items():
            cmd += ["--data-urlencode", f"{k}={v}"]
    if body is not None:
        cmd += ["-H", "Content-Type: application/json", "-d", json.dumps(body)]
    out = subprocess.check_output(cmd, text=True)
    body_s, code = out.rsplit("__HTTP__", 1)
    try:
        data = json.loads(body_s) if body_s.strip() else {}
    except json.JSONDecodeError:
        data = {"raw": body_s[:500]}
    return data, code.strip()


def apply_ingress(name, host, svc, port):
    yaml = f"""apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {name}
  namespace: prod
  annotations:
    traefik.ingress.kubernetes.io/router.entrypoints: web
spec:
  ingressClassName: traefik
  rules:
  - host: {host}
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: {svc}
            port:
              number: {port}
"""
    path = f"/tmp/ing-{name}.yaml"
    Path(path).write_text(yaml)
    sh(f"k3s kubectl apply -f {path}")


def main():
    cfg = load_env()
    print("=== 1) Reset n8n PVCs (encryption key mismatch) ===")
    for ns in ("prod", "dev"):
        sh(f"k3s kubectl -n {ns} delete sts lab-n8n --wait=false")
        time.sleep(3)
        sh(f"k3s kubectl -n {ns} delete pvc data-lab-n8n-0 --wait=false")
    print("waiting ArgoCD recreate n8n...")
    time.sleep(20)
    for i in range(24):
        rc, out = sh(
            "k3s kubectl -n prod get pod lab-n8n-0 -o jsonpath='{.status.phase}' 2>/dev/null"
        )
        print(f"  prod n8n phase={out!r}")
        if out == "Running":
            # confirm not crashloop
            rc2, restarts = sh(
                "k3s kubectl -n prod get pod lab-n8n-0 -o jsonpath='{.status.containerStatuses[0].restartCount}'"
            )
            print(f"  restarts={restarts}")
            if restarts in ("0", "1", ""):
                break
        time.sleep(10)

    print("\n=== 2) Public ingress for n8n + emqx dashboard ===")
    apply_ingress("lab-n8n", "lab-n8n.softwarefactory.site", "lab-n8n", 5678)
    apply_ingress("lab-emqx-dashboard", "lab-emqx.softwarefactory.site", "lab-emqx", 18083)

    print("\n=== 3) Redeploy lab-react (prod+dev only — avoid staging patch bug) ===")
    auth, _ = curl_json(
        "POST", "/api/v1/auth/token",
        form={"username": cfg["KAANBAL_ADMIN_USER"], "password": cfg["KAANBAL_ADMIN_PASS"]},
    )
    token = auth["access_token"]
    apps, _ = curl_json("GET", "/api/v1/apps", token=token)
    for a in apps if isinstance(apps, list) else []:
        if a.get("name") == "lab-react":
            aid = a.get("_id") or a.get("id")
            print("DELETE lab-react", aid)
            curl_json("DELETE", f"/api/v1/apps/{aid}", token=token)
    time.sleep(5)
    data, code = curl_json(
        "POST", "/api/v1/apps", token=token,
        body={
            "name": "lab-react",
            "template": "react-spa",
            "category": "frontend",
            "environments": ["dev", "prod"],
            "creation_mode": "scaffold",
            "exposure": {
                "type": "public",
                "per_env": {"prod": "public", "dev": "tailscale"},
            },
        },
    )
    print("lab-react deploy", code, json.dumps(data)[:250])

    print("\n=== 4) Validation ===")
    time.sleep(15)
    for url in (
        "https://lab-pg.softwarefactory.site/",
        "https://lab-mongo.softwarefactory.site/",
        "https://lab-api.softwarefactory.site/health",
        "https://lab-emqx.softwarefactory.site/",
        "https://lab-n8n.softwarefactory.site/",
    ):
        sh(f"curl -sS -o /dev/null -w '{url} -> %{{http_code}}\\n' --max-time 12 '{url}'")

    sh("k3s kubectl -n prod exec deploy/lab-api -- env | grep -E 'DB_HOST|MONGO_HOST'")
    print("FIXUPS_DONE")


if __name__ == "__main__":
    main()
