#!/usr/bin/env python3
"""Smoke: deploy MongoDB + PostgreSQL (config-only, tailscale) and verify Vault paths."""
import json
import subprocess
import sys
import time

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


def deploy(token, name, template):
    payload = {
        "name": name,
        "template": template,
        "category": "database",
        "environments": ["dev", "prod"],
        "creation_mode": "config-only",
        "exposure": {
            "type": "tailscale",
            "per_env": {"dev": "tailscale", "prod": "tailscale"},
        },
    }
    print(f"=== deploy {name} ({template}) ===")
    resp = curl_json("POST", "/api/v1/apps", token=token, body=payload)
    print(json.dumps(resp, indent=2)[:500])
    return resp


def wait_pod(ns, app, tries=30):
    for i in range(tries):
        r = subprocess.run(
            f"k3s kubectl -n {ns} get deploy,sts -l app={app} -o json",
            shell=True, text=True, capture_output=True,
        )
        try:
            items = json.loads(r.stdout or "{}").get("items") or []
        except json.JSONDecodeError:
            items = []
        ready = False
        for it in items:
            status = it.get("status") or {}
            if status.get("readyReplicas"):
                ready = True
        print(f"  {ns}/{app} try={i} ready={ready} kinds={[it.get('kind') for it in items]}")
        if ready:
            return True
        time.sleep(10)
    return False


def main():
    cfg = load_env()
    tok = curl_json(
        "POST", "/api/v1/auth/token",
        form={"username": cfg.get("KAANBAL_ADMIN_USER", "andresbc"),
              "password": cfg.get("KAANBAL_ADMIN_PASS", "")},
    )
    token = tok["access_token"]
    print("auth OK")

    # Refresh templates from GitHub
    try:
        curl_json("GET", "/api/v1/templates/refresh", token=token)
        print("templates refreshed")
    except Exception as exc:
        print("refresh warn:", exc)

    templates = curl_json("GET", "/api/v1/templates", token=token)
    items = templates if isinstance(templates, list) else templates.get("templates") or []
    ids = [t.get("id") for t in items if isinstance(t, dict)]
    print("catalog ids:", ids)

    for needed in ("mongodb", "postgres", "emqx", "n8n", "react-spa"):
        if needed not in ids:
            print(f"MISSING template: {needed}")

    deploy(token, "lab-mongo", "mongodb")
    deploy(token, "lab-pg", "postgres")

    time.sleep(20)
    ok_m = wait_pod("prod", "lab-mongo") and wait_pod("dev", "lab-mongo")
    ok_p = wait_pod("prod", "lab-pg") and wait_pod("dev", "lab-pg")

    print("=== vault secrets (list) ===")
    try:
        secrets = curl_json("GET", "/api/v1/system/vault/secrets", token=token)
        print(json.dumps(secrets, indent=2)[:1200])
    except Exception as exc:
        print("vault list error:", exc)

    for app in ("lab-mongo", "lab-pg"):
        for env in ("prod", "dev"):
            try:
                sec = curl_json("GET", f"/api/v1/system/vault/secrets/{env}/{app}?reveal=false", token=token)
                keys = list((sec.get("data") or sec.get("secrets") or sec).keys()) if isinstance(sec, dict) else sec
                print(f"vault {env}/{app} keys={keys}")
            except Exception as exc:
                print(f"vault {env}/{app} error: {exc}")

    print("RESULT", "OK" if ok_m and ok_p else "PARTIAL", f"mongo={ok_m} postgres={ok_p}")
    return 0 if ok_m and ok_p else 1


if __name__ == "__main__":
    sys.exit(main())
