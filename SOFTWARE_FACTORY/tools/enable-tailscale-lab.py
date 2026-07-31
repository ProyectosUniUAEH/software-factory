#!/usr/bin/env python3
"""Activa Tailscale en un lab ya instalado: ACL + secret + Application ArgoCD.

Uso (en el servidor):
  sudo python3 tools/enable-tailscale-lab.py
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

ENV_FILE = "/etc/kaanbal/installer.env"
INSTALLER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "installer")
sys.path.insert(0, INSTALLER)

import server  # noqa: E402


def load_env(path):
    data = {}
    with open(path, encoding="utf-8") as f:
        for line in f.read().replace("\r", "").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            data[k.strip()] = v.strip()
    return data


def sh(cmd, check=True):
    print(f"$ {cmd}")
    r = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    if r.stdout:
        print(r.stdout.rstrip())
    if r.returncode != 0 and check:
        print(r.stderr.rstrip(), file=sys.stderr)
        sys.exit(r.returncode)
    return r


def main():
    cfg = load_env(ENV_FILE)
    cid = cfg.get("TAILSCALE_CLIENT_ID", "")
    csec = cfg.get("TAILSCALE_CLIENT_SECRET", "")
    org = cfg.get("GITHUB_ORG", "ProyectosUniUAEH")
    if not cid or not csec:
        print("ERROR: faltan TAILSCALE_CLIENT_* en installer.env")
        return 1

    print("=== 1. ACL tagOwners ===")
    ok, why = server.ensure_tailscale_acl_tags(cid, csec, log_fn=lambda m, l="info": print(f"[{l}] {m}"))
    if not ok:
        print("FAIL ACL:", why)
        return 1

    print("=== 2. can mint tag:k8s-operator ===")
    can, detail = server.tailscale_can_tag(cid, csec)
    print("can_tag:", can, detail or "OK")
    if not can:
        return 1

    print("=== 3. namespace + oauth secret ===")
    sh("k3s kubectl create namespace tailscale --dry-run=client -o yaml | k3s kubectl apply -f -")
    sh(
        "k3s kubectl -n tailscale create secret generic operator-oauth "
        f"--from-literal=client_id='{cid}' --from-literal=client_secret='{csec}' "
        "--dry-run=client -o yaml | k3s kubectl apply -f -"
    )

    print("=== 4. ArgoCD Application ===")
    app = f"""apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: tailscale-operator
  namespace: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: software-factory
  source:
    repoURL: https://github.com/{org}/infra-gitops.git
    targetRevision: HEAD
    path: apps/tailscale-operator/overlays/dev
  destination:
    server: https://kubernetes.default.svc
    namespace: tailscale
  ignoreDifferences:
    - group: apps
      kind: StatefulSet
      managedFieldsManagers:
        - tailscale-operator
    - group: ""
      kind: Secret
      managedFieldsManagers:
        - tailscale-operator
  syncPolicy:
    automated:
      prune: false
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
      - ServerSideApply=true
      - ApplyOutOfSyncOnly=true
"""
    path = "/tmp/tailscale-operator-app.yaml"
    with open(path, "w", encoding="utf-8") as f:
        f.write(app)
    sh(f"k3s kubectl apply -f {path}")

    print("=== 5. esperar operador ===")
    sh("k3s kubectl -n tailscale rollout status deploy/operator --timeout=180s", check=False)
    sh("k3s kubectl -n tailscale get pods,svc 2>/dev/null || true", check=False)
    print("ENABLE_TAILSCALE_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
