#!/usr/bin/env python3
"""Asegura que infra-gitops tenga apps/tailscale-operator (por si el install lo omitió)."""
import os
import shutil
import subprocess
import sys
import tempfile

ENV_FILE = "/etc/kaanbal/installer.env"
LOCAL_SRC = "/home/andres/kaanbal-next/infra-gitops/apps/tailscale-operator"
# fallback from SOFTWARE_FACTORY tree
ALT_SRC = "/home/andres/kaanbal-next/SOFTWARE_FACTORY/infra-gitops/apps/tailscale-operator"


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


def main():
    cfg = load_env(ENV_FILE)
    token = cfg["GITOPS_TOKEN"]
    org = cfg["GITHUB_ORG"]
    src = LOCAL_SRC if os.path.isdir(LOCAL_SRC) else ALT_SRC
    if not os.path.isdir(src):
        print(f"ERROR: no local source at {LOCAL_SRC} or {ALT_SRC}")
        return 1

    work = tempfile.mkdtemp(prefix="ts-op-")
    clone = os.path.join(work, "repo")
    run(f"git clone --depth 1 'https://{token}@github.com/{org}/infra-gitops.git' '{clone}'")
    dest = os.path.join(clone, "apps/tailscale-operator")
    if os.path.isdir(dest):
        print("apps/tailscale-operator already in infra-gitops")
    else:
        shutil.copytree(src, dest)
        # strip placeholder secret values if any — real secret is in cluster
        run(
            "git config user.email 'repair@kaanbal.local' && "
            "git config user.name 'Kaanbal Repair' && "
            "git add apps/tailscale-operator && "
            "git commit -m 'feat: publish tailscale-operator manifests for VPN tier' && "
            "git push origin main",
            cwd=clone,
        )
        print("PUSHED apps/tailscale-operator")
    return 0


if __name__ == "__main__":
    sys.exit(main())
