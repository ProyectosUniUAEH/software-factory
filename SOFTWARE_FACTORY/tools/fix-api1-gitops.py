#!/usr/bin/env python3
"""Fix api1 staging host in infra-gitops (same bug as front1)."""
import os, re, subprocess, sys, tempfile

cfg = {}
for line in open("/etc/kaanbal/installer.env"):
    line = line.strip().replace("\r", "")
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        cfg[k] = v

APP = "api1"
DOMAIN = cfg.get("DOMAIN", "softwarefactory.site")
token, org = cfg["GITOPS_TOKEN"], cfg["GITHUB_ORG"]
work = tempfile.mkdtemp()
clone = f"{work}/repo"
subprocess.check_call(
    f"git clone --depth 1 https://{token}@github.com/{org}/infra-gitops.git {clone}",
    shell=True,
)

def strip_patches(c):
    return re.sub(r"\npatches:[\s\S]*", "", c)

staging_host = f"staging-{APP}.{DOMAIN}"
staging = os.path.join(clone, f"apps/{APP}/overlays/staging/kustomization.yaml")
dev = os.path.join(clone, f"apps/{APP}/overlays/dev/kustomization.yaml")

with open(staging, encoding="utf-8") as f:
    s = strip_patches(f.read()).rstrip()
s += f"""

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
open(staging, "w", encoding="utf-8").write(s)

with open(dev, encoding="utf-8") as f:
    d = strip_patches(f.read()).rstrip()
d += f"""

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
open(dev, "w", encoding="utf-8").write(d)

subprocess.check_call(
    "git config user.email repair@kaanbal.local && git config user.name Kaanbal && "
    "git add -A && git commit -m 'fix(api1): staging host prefix + dev tailscale-only' && "
    "git push origin main",
    shell=True, cwd=clone,
)
print("PUSH_OK", staging_host)
