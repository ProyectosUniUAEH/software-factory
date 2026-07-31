#!/usr/bin/env python3
"""Fix seed (github + username), refresh templates, delete failed apps, redeploy DBs+stack."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

API = "https://kaanbal-api.softwarefactory.site"


def load_env(path="/etc/kaanbal/installer.env"):
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
        data = {"raw": body_s[:800]}
    return data, code.strip()


def github_login(token: str) -> str:
    out = subprocess.check_output(
        [
            "curl", "-sS",
            "-H", f"Authorization: Bearer {token}",
            "-H", "Accept: application/vnd.github+json",
            "-H", "User-Agent: kaanbal-fix",
            "https://api.github.com/user",
        ],
        text=True,
    )
    data = json.loads(out)
    login = data.get("login") or ""
    print(f"github login={login}")
    return login


def vault_token():
    rc, out, _ = sh(
        "k3s kubectl -n vault get secret vault-init-keys "
        "-o jsonpath='{.data.root-token}'"
    )
    if rc == 0 and out:
        import base64
        return base64.b64decode(out.strip().strip("'")).decode()
    return ""


def argo_password():
    import base64
    rc, out, _ = sh(
        "k3s kubectl -n argocd get secret argocd-initial-admin-secret "
        "-o jsonpath='{.data.password}'"
    )
    if rc != 0 or not out:
        return ""
    return base64.b64decode(out.strip().strip("'")).decode()


def main():
    cfg = load_env()
    git_token = cfg["GITOPS_TOKEN"]
    login = github_login(git_token) or cfg.get("GITHUB_ORG", "kaanbal")

    payload = {
        "mode": "cloud",
        "domain": (cfg.get("DOMAIN") or "").strip().lower(),
        "git_provider": "github",
        "git_username": login,
        "git_token": git_token,
        "git_workspace": (cfg.get("GITHUB_ORG") or "").strip(),
        "github_is_org": True,
        "dockerhub_username": (cfg.get("DOCKER_USER") or "").strip(),
        "dockerhub_token": (cfg.get("DOCKER_TOKEN") or "").strip(),
        "tailscale_client_id": (cfg.get("TAILSCALE_CLIENT_ID") or "").strip(),
        "tailscale_client_secret": (cfg.get("TAILSCALE_CLIENT_SECRET") or "").strip(),
        "tailscale_dns_suffix": (cfg.get("TAILSCALE_DNS_SUFFIX") or "").strip(),
        "cloudflare_token": (cfg.get("CF_TOKEN") or "").strip(),
        "cloudflare_account_id": (cfg.get("CF_ACCOUNT_ID") or "").strip(),
        "ingress_class": "traefik",
        "ingress_cluster_issuer": "",
        "argocd_password": argo_password(),
        "argocd_server": "https://argocd-server.argocd.svc.cluster.local:443",
        "vault_addr": "http://vault.vault.svc.cluster.local:8200",
        "vault_token": vault_token(),
        "templates_repo": "kaanbal-templates",
        "admin_user": cfg["KAANBAL_ADMIN_USER"],
        "admin_password": cfg["KAANBAL_ADMIN_PASS"],
    }
    print("re-seed github_user=", login, "org=", payload["git_workspace"])
    data, code = curl_json("POST", "/api/v1/setup/install", body=payload)
    print("setup", code, json.dumps(data)[:200])
    if code not in ("200", "201"):
        return 1

    auth, _ = curl_json(
        "POST", "/api/v1/auth/token",
        form={"username": cfg["KAANBAL_ADMIN_USER"], "password": cfg["KAANBAL_ADMIN_PASS"]},
    )
    token = auth["access_token"]
    print("auth OK")

    # Refresh templates
    data, code = curl_json("GET", "/api/v1/templates/refresh", token=token)
    print("templates refresh", code, json.dumps(data)[:400])
    data, code = curl_json("GET", "/api/v1/templates", token=token)
    names = []
    if isinstance(data, list):
        names = [t.get("id") or t.get("name") for t in data]
    elif isinstance(data, dict):
        items = data.get("templates") or data.get("items") or data.get("data") or []
        names = [t.get("id") or t.get("name") for t in items]
    print("catalog:", names)

    # Delete failed apps
    apps, _ = curl_json("GET", "/api/v1/apps", token=token)
    if isinstance(apps, dict):
        apps = apps.get("apps") or apps.get("items") or []
    for app in apps or []:
        name = app.get("name") or ""
        aid = str(app.get("id") or app.get("_id") or "")
        if name.startswith("lab-") and aid:
            print(f"DELETE {name}")
            curl_json("DELETE", f"/api/v1/apps/{aid}", token=token)

    print("FIX_SEED_DONE — launching mixed redeploy")
    # exec wipe script deploy mode
    rc = subprocess.call(["python3", "-u", "/tmp/wipe-and-redeploy-v1-mixed.py", "deploy"])
    return rc


if __name__ == "__main__":
    sys.exit(main())
