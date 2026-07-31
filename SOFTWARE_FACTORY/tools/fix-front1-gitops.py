#!/usr/bin/env python3
"""Fix front1 in infra-gitops: staging host prefix + dev tailscale-only."""
import os
import re
import subprocess
import sys
import tempfile

ENV_FILE = "/etc/kaanbal/installer.env"
REPO = "infra-gitops"
APP = "front1"


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


def run(cmd, cwd=None):
    r = subprocess.run(cmd, shell=True, cwd=cwd, text=True, capture_output=True)
    if r.returncode != 0:
        print(r.stderr or r.stdout, file=sys.stderr)
        sys.exit(r.returncode)
    return r.stdout


def strip_patches(content):
    return re.sub(r"\npatches:[\s\S]*", "", content)


def main():
    cfg = load_env(ENV_FILE)
    token = cfg["GITOPS_TOKEN"]
    org = cfg["GITHUB_ORG"]
    domain = cfg.get("DOMAIN", "softwarefactory.site")

    work = tempfile.mkdtemp(prefix="fix-front1-")
    clone = os.path.join(work, "repo")
    run(f"git clone --depth 1 'https://{token}@github.com/{org}/{REPO}.git' '{clone}'")

    staging_host = f"staging-{APP}.{domain}"
    staging_kust = os.path.join(clone, f"apps/{APP}/overlays/staging/kustomization.yaml")
    dev_kust = os.path.join(clone, f"apps/{APP}/overlays/dev/kustomization.yaml")

    with open(staging_kust, encoding="utf-8") as f:
        staging = strip_patches(f.read()).rstrip()
    staging += f"""

patches:
  - target:
      kind: Ingress
      name: {APP}
    patch: |-
      - op: replace
        path: /spec/rules/0/host
        value: {staging_host}
      - op: replace
        path: /spec/tls/0/hosts/0
        value: {staging_host}
      - op: replace
        path: /spec/tls/0/secretName
        value: tls-staging-{APP}
"""
    with open(staging_kust, "w", encoding="utf-8") as f:
        f.write(staging)
    print(f"updated staging -> {staging_host}")

    with open(dev_kust, encoding="utf-8") as f:
        dev = strip_patches(f.read()).rstrip()
    dev += f"""

patches:
  - target:
      kind: Ingress
      name: {APP}
    patch: |-
      $patch: delete
      apiVersion: networking.k8s.io/v1
      kind: Ingress
      metadata:
        name: {APP}
"""
    with open(dev_kust, "w", encoding="utf-8") as f:
        f.write(dev)
    print("updated dev -> ingress deleted (tailscale only)")

    run(
        "git config user.email 'repair@kaanbal.local' && "
        "git config user.name 'Kaanbal Repair' && "
        "git add -A && git commit -m "
        "'fix(front1): staging host prefix + dev tailscale-only ingress'",
        cwd=clone,
    )
    run("git push origin main", cwd=clone)
    print("PUSH_OK")


if __name__ == "__main__":
    main()
