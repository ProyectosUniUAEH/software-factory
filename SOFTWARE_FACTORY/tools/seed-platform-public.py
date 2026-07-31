#!/usr/bin/env python3
"""Seed platform config via public API (no port-forward)."""
from __future__ import annotations

import base64
import json
import subprocess
import sys
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


def curl_json(method, path, body=None, token=None):
    cmd = ["curl", "-sS", "-w", "\n__HTTP__%{http_code}", "-X", method, f"{API}{path}"]
    if token:
        cmd += ["-H", f"Authorization: Bearer {token}"]
    if body is not None:
        cmd += ["-H", "Content-Type: application/json", "-d", json.dumps(body)]
    out = subprocess.check_output(cmd, text=True)
    body_s, code = out.rsplit("__HTTP__", 1)
    try:
        data = json.loads(body_s) if body_s.strip() else {}
    except json.JSONDecodeError:
        data = {"raw": body_s[:500]}
    return data, code.strip()


def vault_token():
    rc, out, _ = sh(
        "k3s kubectl -n vault get secret vault-init-keys "
        "-o jsonpath='{.data.root-token}'"
    )
    if rc == 0 and out:
        return base64.b64decode(out.strip().strip("'")).decode()
    return ""


def argo_password():
    rc, out, _ = sh(
        "k3s kubectl -n argocd get secret argocd-initial-admin-secret "
        "-o jsonpath='{.data.password}'"
    )
    if rc != 0 or not out:
        return ""
    return base64.b64decode(out.strip().strip("'")).decode()


def github_login(token: str) -> str:
    try:
        out = subprocess.check_output(
            [
                "curl", "-sS",
                "-H", f"Authorization: Bearer {token}",
                "-H", "Accept: application/vnd.github+json",
                "-H", "User-Agent: kaanbal-seed",
                "https://api.github.com/user",
            ],
            text=True,
        )
        return json.loads(out).get("login") or ""
    except Exception:
        return ""


def main():
    cfg = load_env()
    git_token = (cfg.get("GITOPS_TOKEN") or "").strip()
    login = (
        (cfg.get("GITHUB_LOGIN") or cfg.get("GITHUB_USER") or "").strip()
        or github_login(git_token)
        or (cfg.get("GITHUB_ORG") or "").strip()
    )
    # Map installer.env keys → setup payload
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
        "tailscale_client_id": (cfg.get("TAILSCALE_CLIENT_ID") or cfg.get("TS_CLIENT_ID") or "").strip(),
        "tailscale_client_secret": (cfg.get("TAILSCALE_CLIENT_SECRET") or cfg.get("TS_CLIENT_SECRET") or "").strip(),
        "tailscale_dns_suffix": (cfg.get("TAILSCALE_DNS_SUFFIX") or cfg.get("TAILSCALE_DNS") or "").strip(),
        "cloudflare_token": (cfg.get("CF_TOKEN") or "").strip(),
        "cloudflare_account_id": (cfg.get("CF_ACCOUNT_ID") or "").strip(),
        "ingress_class": "traefik",
        "ingress_cluster_issuer": "",
        "argocd_password": argo_password(),
        "argocd_server": "https://argocd-server.argocd.svc.cluster.local:443",
        "vault_addr": "http://vault.vault.svc.cluster.local:8200",
        "vault_token": vault_token() or cfg.get("VAULT_TOKEN", ""),
        "templates_repo": "kaanbal-templates",
        "admin_user": (cfg.get("KAANBAL_ADMIN_USER") or "admin").strip(),
        "admin_password": (cfg.get("KAANBAL_ADMIN_PASS") or "").strip(),
    }
    print("domain=", payload["domain"])
    print("org=", payload["git_workspace"])
    print("has_git_token=", bool(payload["git_token"]))
    print("has_docker=", bool(payload["dockerhub_username"] and payload["dockerhub_token"]))
    print("has_ts=", bool(payload["tailscale_client_id"]))
    print("has_vault=", bool(payload["vault_token"]))
    print("has_argo=", bool(payload["argocd_password"]))

    data, code = curl_json("POST", "/api/v1/setup/install", body=payload)
    print("setup/install HTTP", code, json.dumps(data)[:300])
    if code not in ("200", "201"):
        return 1

    # Verify domain via apps list auth
    auth, acode = curl_json(
        "POST",
        "/api/v1/auth/token",
        body=None,
    )
    # auth uses form — call curl manually
    out = subprocess.check_output(
        [
            "curl", "-sS", "-w", "\n__HTTP__%{http_code}", "-X", "POST",
            f"{API}/api/v1/auth/token",
            "--data-urlencode", f"username={payload['admin_user']}",
            "--data-urlencode", f"password={payload['admin_password']}",
        ],
        text=True,
    )
    body_s, acode = out.rsplit("__HTTP__", 1)
    token = json.loads(body_s)["access_token"]
    print("auth OK")

    # Quick check: create should no longer say domain missing — dry by GET templates
    t, tcode = curl_json("GET", "/api/v1/templates", token=token)
    print("templates HTTP", tcode)
    print("SEED_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
