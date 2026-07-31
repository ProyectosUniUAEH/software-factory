#!/usr/bin/env python3
"""Smoke: react-spa, n8n, emqx + optional DB binding to FastAPI."""
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
    cmd = ["curl", "-sS", "-w", "\n__HTTP__%{http_code}", "-X", method, f"{API}{path}"]
    if token:
        cmd += ["-H", f"Authorization: Bearer {token}"]
    if form is not None:
        for k, v in form.items():
            cmd += ["--data-urlencode", f"{k}={v}"]
    if body is not None:
        cmd += ["-H", "Content-Type: application/json", "-d", json.dumps(body)]
    out = subprocess.check_output(cmd, text=True)
    if "__HTTP__" in out:
        body_s, code = out.rsplit("__HTTP__", 1)
        code = code.strip()
    else:
        body_s, code = out, "?"
    try:
        data = json.loads(body_s) if body_s.strip() else {}
    except json.JSONDecodeError:
        data = {"raw": body_s[:500]}
    return data, code


def auth():
    cfg = load_env()
    data, code = curl_json(
        "POST", "/api/v1/auth/token",
        form={
            "username": cfg.get("KAANBAL_ADMIN_USER", "andresbc"),
            "password": cfg.get("KAANBAL_ADMIN_PASS", ""),
        },
    )
    if code != "200" or "access_token" not in data:
        raise SystemExit(f"auth failed {code} {data}")
    return data["access_token"]


def deploy(token, name, template, category, creation_mode, exposure, extra=None):
    payload = {
        "name": name,
        "template": template,
        "category": category,
        "environments": ["dev", "prod"],
        "creation_mode": creation_mode,
        "exposure": exposure,
    }
    if extra:
        payload.update(extra)
    print(f"\n=== deploy {name} ({template}) ===")
    data, code = curl_json("POST", "/api/v1/apps", token=token, body=payload)
    print(f"HTTP {code}", json.dumps(data, indent=2)[:600])
    return data, code


def wait_ready(ns, app, kinds=("Deployment", "StatefulSet"), tries=36):
    for i in range(tries):
        r = subprocess.run(
            ["k3s", "kubectl", "-n", ns, "get", "deploy,sts", "-l", f"app={app}", "-o", "json"],
            text=True, capture_output=True,
        )
        try:
            items = json.loads(r.stdout or "{}").get("items") or []
        except json.JSONDecodeError:
            items = []
        ready = any((it.get("status") or {}).get("readyReplicas") for it in items)
        print(f"  wait {ns}/{app} i={i} ready={ready} {[it.get('kind') for it in items]}")
        if ready:
            return True
        time.sleep(10)
    return False


def http_ok(url):
    r = subprocess.run(
        ["curl", "-sS", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", "20", url],
        text=True, capture_output=True,
    )
    code = (r.stdout or "").strip()
    print(f"  GET {url} -> {code}")
    return code in ("200", "301", "302", "401", "403")  # n8n may redirect/auth


def main():
    token = auth()
    print("auth OK")
    curl_json("GET", "/api/v1/templates/refresh", token=token)

    # 1) React public prod + tailscale dev
    deploy(
        token, "lab-react", "react-spa", "frontend", "scaffold",
        {"type": "public", "per_env": {"prod": "public", "dev": "tailscale"}},
    )

    # 2) n8n — UI VPN; webhooks can be both if supported
    deploy(
        token, "lab-n8n", "n8n", "workflow", "config-only",
        {"type": "tailscale", "per_env": {"prod": "tailscale", "dev": "tailscale"}},
    )

    # 3) EMQX — VPN only (iot)
    deploy(
        token, "lab-emqx", "emqx", "iot", "config-only",
        {"type": "tailscale", "per_env": {"prod": "tailscale", "dev": "tailscale"}},
    )

    # 4) FastAPI bound to lab-pg (secure DB link)
    deploy(
        token, "lab-api-bound", "fastapi-api", "backend", "scaffold",
        {"type": "public", "per_env": {"prod": "public", "dev": "tailscale"}},
        extra={
            "database_bindings": {
                "prod": [{"app_name": "lab-pg", "env": "prod", "alias": "DB", "template": "postgres"}],
                "dev": [{"app_name": "lab-pg", "env": "dev", "alias": "DB", "template": "postgres"}],
            }
        },
    )

    print("\n=== waiting pods ===")
    time.sleep(30)
    results = {
        "lab-react": wait_ready("prod", "lab-react"),
        "lab-n8n": wait_ready("prod", "lab-n8n"),
        "lab-emqx": wait_ready("prod", "lab-emqx"),
        "lab-api-bound": wait_ready("prod", "lab-api-bound"),
    }

    print("\n=== HTTP checks ===")
    http_ok("https://lab-react.softwarefactory.site/")
    http_ok("https://lab-api-bound.softwarefactory.site/health")

    print("\n=== Tailscale devices (filter) ===")
    subprocess.run("sudo python3 /tmp/list-ts-devices.py 2>/dev/null | grep -iE 'lab-|n8n|emqx|react' || true", shell=True)

    print("\n=== Vault / env injection check (api-bound) ===")
    # Inspect kustomize secret literals via kubectl if secret exists
    for env in ("prod", "dev"):
        r = subprocess.run(
            f"k3s kubectl -n {env} get secret lab-api-bound-secrets -o json 2>/dev/null",
            shell=True, text=True, capture_output=True,
        )
        if r.returncode != 0:
            print(f"  {env}: secret not found yet")
            continue
        sec = json.loads(r.stdout)
        keys = sorted((sec.get("data") or {}).keys())
        print(f"  {env} lab-api-bound-secrets keys={keys}")
        has_db = any(k.startswith("DB_") for k in keys)
        print(f"  {env} has DB_* bindings: {has_db}")

    print("\n=== RESULT ===")
    print(json.dumps(results, indent=2))
    ok = all(results.values())
    print("OK" if ok else "PARTIAL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
