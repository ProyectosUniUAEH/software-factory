#!/usr/bin/env python3
"""Force-update kaanbal-templates on GitHub from local tree."""
import os
import shutil
import subprocess
import sys
import tempfile

ENV = "/etc/kaanbal/installer.env"
SRC = "/home/andres/kaanbal-next/kaanbal-templates"


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
    cfg = load_env(ENV)
    token, org = cfg["GITOPS_TOKEN"], cfg["GITHUB_ORG"]
    work = tempfile.mkdtemp(prefix="tpl-upd-")
    clone = os.path.join(work, "repo")
    run(f"git clone --depth 1 https://{token}@github.com/{org}/kaanbal-templates.git {clone}")

    # Replace tracked content (keep .git)
    for name in os.listdir(clone):
        if name == ".git":
            continue
        path = os.path.join(clone, name)
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)

    for name in os.listdir(SRC):
        src = os.path.join(SRC, name)
        dst = os.path.join(clone, name)
        if os.path.isdir(src):
            shutil.copytree(
                src, dst,
                ignore=shutil.ignore_patterns(".git", "node_modules", "__pycache__", "dist"),
            )
        else:
            shutil.copy2(src, dst)

    run(
        "git config user.email repair@kaanbal.local && "
        "git config user.name Kaanbal && "
        "git add -A && "
        "git diff --cached --quiet || git commit -m 'feat: v1 catalog — react, postgres, emqx, enrich mongo/n8n' && "
        "git push origin main",
        cwd=clone,
    )
    sha = run("git rev-parse HEAD", cwd=clone).strip()
    print("PUSH_OK", sha[:7])
    return 0


if __name__ == "__main__":
    sys.exit(main())
