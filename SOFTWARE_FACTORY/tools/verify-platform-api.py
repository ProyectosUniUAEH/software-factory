#!/usr/bin/env python3
"""Verifica ArgoCD y Vault vía API pública (requiere KAANBAL_PASS en env)."""
import json
import os
import subprocess
import sys

API = os.environ.get("API_URL", "https://kaanbal-api.softwarefactory.site")
USER = os.environ.get("KAANBAL_USER", "andresbc")
PASS = os.environ.get("KAANBAL_PASS")
if not PASS:
    print("ERROR: set KAANBAL_PASS", file=sys.stderr)
    sys.exit(2)


def curl_json(method: str, path: str, token: str | None = None, form: dict | None = None) -> dict:
    cmd = ["curl", "-sS", "-X", method, f"{API}{path}"]
    if token:
        cmd += ["-H", f"Authorization: Bearer {token}"]
    if form:
        for key, value in form.items():
            cmd += ["--data-urlencode", f"{key}={value}"]
    out = subprocess.check_output(cmd, text=True)
    return json.loads(out)


def main() -> int:
    ok = True
    try:
        tok = curl_json("POST", "/api/v1/auth/token", form={"username": USER, "password": PASS})
        token = tok["access_token"]
    except (subprocess.CalledProcessError, KeyError, json.JSONDecodeError) as exc:
        print(f"AUTH FAIL: {exc}")
        return 1

    print("=== ArgoCD ===")
    try:
        argo = curl_json("GET", "/api/v1/apps/argocd/all", token=token)
        connected = argo.get("connected")
        count = argo.get("count")
        reason = argo.get("connection_reason", "")
        print(f"connected: {connected}")
        print(f"count: {count}")
        print(f"reason: {reason}")
        if not connected or (count or 0) == 0:
            ok = False
    except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"ARGO FAIL: {exc}")
        ok = False

    print("=== Vault ===")
    try:
        vault = curl_json("GET", "/api/v1/system/vault/status", token=token)
        configured = vault.get("configured")
        sealed = vault.get("sealed")
        reachable = vault.get("reachable")
        print(f"configured: {configured}")
        print(f"sealed: {sealed}")
        print(f"reachable: {reachable}")
        if not configured or sealed:
            ok = False
    except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"VAULT FAIL: {exc}")
        ok = False

    print("=== RESULT ===")
    print("OK" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
