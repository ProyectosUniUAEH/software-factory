#!/usr/bin/env python3
"""Smoke deploy: FastAPI via API (scaffold + public prod)."""
import json
import os
import subprocess
import sys
import time
import urllib.parse

API = os.environ.get("API_URL", "https://kaanbal-api.softwarefactory.site")
APP = os.environ.get("APP_NAME", "api1")


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


def curl_json(method, path, token=None, form=None, body=None):
    cmd = ["curl", "-sS", "-X", method, f"{API}{path}"]
    if token:
        cmd += ["-H", f"Authorization: Bearer {token}"]
    if form is not None:
        for k, v in form.items():
            cmd += ["--data-urlencode", f"{k}={v}"]
    if body is not None:
        cmd += ["-H", "Content-Type: application/json", "-d", json.dumps(body)]
    out = subprocess.check_output(cmd, text=True)
    return json.loads(out) if out.strip() else {}


def main():
    cfg = load_env()
    user = cfg.get("KAANBAL_ADMIN_USER", "andresbc")
    password = cfg.get("KAANBAL_ADMIN_PASS", "")
    tok = curl_json("POST", "/api/v1/auth/token", form={"username": user, "password": password})
    token = tok["access_token"]
    print("auth OK")

    # List templates
    templates = curl_json("GET", "/api/v1/templates", token=token)
    items = templates if isinstance(templates, list) else templates.get("templates") or templates.get("items") or []
    ids = [t.get("id") or t.get("template_id") or t.get("name") for t in items if isinstance(t, dict)]
    print("templates:", ids)

    payload = {
        "name": APP,
        "template": "fastapi-api",
        "category": "backend",
        "environments": ["dev", "staging", "prod"],
        "creation_mode": "scaffold",
        "exposure": {
            "type": "public",
            "per_env": {
                "prod": "public",
                "staging": "public",
                "dev": "tailscale",
            },
        },
    }
    print("deploying", payload)
    resp = curl_json("POST", "/api/v1/apps", token=token, body=payload)
    print("response:", json.dumps(resp, indent=2)[:800])
    stream = resp.get("stream_url") or f"/api/v1/apps/{APP}/deploy/stream"
    print("stream:", stream)

    # Poll status a few times
    for i in range(24):
        time.sleep(15)
        try:
            st = curl_json("GET", f"/api/v1/apps/{APP}/status/full", token=token)
        except Exception as exc:
            print(f"poll{i} error: {exc}")
            continue
        print(f"poll{i}: status={st.get('status')} envs={list((st.get('environments') or {}).keys()) if isinstance(st.get('environments'), dict) else st.get('environments')}")
        # stop early if prod healthy-ish
        if st.get("status") in ("running", "healthy", "deployed", "ready"):
            break
    print("SMOKE_DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
