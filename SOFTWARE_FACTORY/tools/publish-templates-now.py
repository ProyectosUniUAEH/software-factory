#!/usr/bin/env python3
"""Sync local kaanbal-templates to server path and publish to GitHub."""
import os
import shutil
import subprocess
import sys
import tempfile

ENV = "/etc/kaanbal/installer.env"
# Prefer the Windows-synced tree if present; else local lab copy
CANDIDATES = [
    "/home/andres/kaanbal-next/kaanbal-templates",
    "/tmp/kaanbal-templates-upload",
]


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


def main():
    cfg = load_env(ENV)
    token, org = cfg["GITOPS_TOKEN"], cfg["GITHUB_ORG"]
    src = next((p for p in CANDIDATES if os.path.isdir(p) and os.path.isfile(f"{p}/catalog.json")), None)
    if not src:
        print("ERROR: no kaanbal-templates source")
        return 1
    print("source:", src)

    sys.path.insert(0, "/home/andres/kaanbal-next/installer")
    import gitops_publish
    from server import run

    sha, err = gitops_publish.publish_source(
        run, token, org, "kaanbal-templates", src, log_fn=print
    )
    if err:
        print("ERROR:", err)
        return 1
    print("OK", (sha or "")[:7])
    return 0


if __name__ == "__main__":
    sys.exit(main())
