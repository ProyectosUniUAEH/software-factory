#!/usr/bin/env python3
"""Restore ArgoCD app-of-apps after accidental wipe of platform Applications."""
from __future__ import annotations

import re
import subprocess
import sys
import time

BOOT = "/home/andres/kaanbal-next/infra-gitops/argocd/bootstrap/app-of-apps.yaml"
ENV = "/etc/kaanbal/installer.env"
FALLBACK_REPO = "https://github.com/ProyectosUniUAEH/infra-gitops.git"

# Never delete these ArgoCD Application names during user-app wipes
PROTECTED_APPS = {
    "applicationsets",
    "core-config",
    "vault",
    "tailscale-operator",
    "root",
    "app-of-apps",
}


def load_env(path=ENV):
    data = {}
    with open(path, encoding="utf-8") as f:
        for line in f.read().replace("\r", "").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            data[k.strip()] = v.strip()
    return data


def sh(cmd):
    r = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()


def main():
    cfg = load_env()
    repo = (
        cfg.get("KAANBAL_GITOPS_REPO_URL")
        or cfg.get("GITOPS_URL")
        or cfg.get("GITOPS_REPO_URL")
        or FALLBACK_REPO
    )
    print(f"gitops repo: {repo}")

    with open(BOOT, encoding="utf-8") as f:
        raw = f.read().replace("\r", "")

    rendered = raw.replace("${KAANBAL_GITOPS_REPO_URL}", repo)
    # Keep Tailscale section (lab has it)
    out = "/tmp/app-of-apps-rendered.yaml"
    with open(out, "w", encoding="utf-8") as f:
        f.write(rendered)

    print(f"applying {out}")
    rc, stdout, stderr = sh(f"k3s kubectl apply -f {out}")
    print(stdout or stderr)
    if rc != 0:
        raise SystemExit(f"kubectl apply failed: {stderr}")

    print("waiting for applicationsets Application + ApplicationSets...")
    for i in range(36):
        rc, out1, _ = sh("k3s kubectl -n argocd get application applicationsets -o jsonpath='{.status.sync.status}'")
        rc2, out2, _ = sh("k3s kubectl -n argocd get applicationset -o name")
        rc3, out3, _ = sh("k3s kubectl -n argocd get applications -o name")
        print(f"  i={i} applicationsets.sync={out1!r} sets={out2!r}")
        print(f"     apps={out3}")
        if "kaanbal-api-prod" in out3 or "application.argoproj.io/kaanbal-api-prod" in out3:
            break
        time.sleep(10)

    print("waiting for kaanbal-api deploy...")
    for i in range(48):
        rc, outp, _ = sh(
            "k3s kubectl -n prod get deploy kaanbal-api -o jsonpath='{.status.readyReplicas}' 2>/dev/null"
        )
        print(f"  api readyReplicas={outp!r}")
        if outp and outp not in ("0", ""):
            break
        time.sleep(10)

    rc, code, _ = sh(
        "curl -sS -o /dev/null -w '%{http_code}' --max-time 15 "
        "https://kaanbal-api.softwarefactory.site/api/v1/health"
    )
    print(f"API health HTTP {code}")
    print("RESTORE_DONE")
    return 0 if code == "200" else 1


if __name__ == "__main__":
    sys.exit(main())
