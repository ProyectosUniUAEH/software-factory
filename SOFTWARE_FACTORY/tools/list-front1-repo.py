#!/usr/bin/env python3
import subprocess, tempfile, sys
from pathlib import Path

cfg = {}
for line in open("/etc/kaanbal/installer.env", encoding="utf-8"):
    line = line.strip().replace("\r", "")
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        cfg[k] = v

work = tempfile.mkdtemp()
subprocess.check_call(
    f"git clone --depth 1 https://{cfg['GITOPS_TOKEN']}@github.com/{cfg['GITHUB_ORG']}/front1.git {work}/repo",
    shell=True,
)
root = Path(work) / "repo"
for p in sorted(root.rglob("*")):
    if p.is_file():
        print(p.relative_to(root))
