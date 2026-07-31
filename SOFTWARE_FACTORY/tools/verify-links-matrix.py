#!/usr/bin/env python3
"""Validate mongo→API binding + ServiceLink API (n8n↔postgres)."""
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
    body_s, code = out.rsplit("__HTTP__", 1) if "__HTTP__" in out else (out, "?")
    try:
        data = json.loads(body_s) if body_s.strip() else {}
    except json.JSONDecodeError:
        data = {"raw": body_s[:400]}
    return data, code.strip()


def sh(cmd):
    r = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    return r.returncode, (r.stdout or "").strip()


def redact_env(lines):
    out = []
    for line in lines:
        k, _, v = line.partition("=")
        if any(x in k for x in ("PASSWORD", "URI", "SECRET", "KEY")):
            out.append(f"{k}=***")
        else:
            out.append(line)
    return out


def main():
    cfg = load_env()
    tok, _ = curl_json(
        "POST", "/api/v1/auth/token",
        form={"username": cfg["KAANBAL_ADMIN_USER"], "password": cfg["KAANBAL_ADMIN_PASS"]},
    )
    token = tok["access_token"]
    print("auth OK")

    # --- Mongo → FastAPI ---
    name = "lab-api-mongo"
    print(f"\n=== deploy {name} bound to lab-mongo ===")
    # delete if exists
    apps, _ = curl_json("GET", "/api/v1/apps", token=token)
    items = apps if isinstance(apps, list) else apps.get("apps") or apps.get("items") or []
    for a in items:
        if a.get("name") == name:
            aid = a.get("id") or a.get("_id")
            if aid:
                curl_json("DELETE", f"/api/v1/apps/{aid}", token=token)
                print("deleted old", name)
                time.sleep(3)

    payload = {
        "name": name,
        "template": "fastapi-api",
        "category": "backend",
        "environments": ["prod"],
        "creation_mode": "scaffold",
        "exposure": {"type": "public", "per_env": {"prod": "public"}},
        "database_bindings": {
            "prod": [{"app_name": "lab-mongo", "env": "prod", "alias": "MONGO", "template": "mongodb"}],
        },
    }
    resp, code = curl_json("POST", "/api/v1/apps", token=token, body=payload)
    print("HTTP", code, resp.get("status") or resp.get("detail") or resp)

    print("waiting rollout...")
    for i in range(30):
        time.sleep(15)
        rc, out = sh("k3s kubectl -n prod get deploy lab-api-mongo -o jsonpath='{.status.readyReplicas}'")
        print(f"  i={i} ready={out}")
        if out == "1":
            break

    rc, out = sh("k3s kubectl -n prod exec deploy/lab-api-mongo -- env")
    mongo_vars = [l for l in out.splitlines() if l.startswith("MONGO_")]
    print("MONGO_* env:")
    for line in redact_env(mongo_vars):
        print(" ", line)

    # --- ServiceLink n8n → postgres ---
    print("\n=== ServiceLink lab-n8n → lab-pg ===")
    link_body = {
        "from_app": "lab-n8n",
        "from_env": "prod",
        "to_app": "lab-pg",
        "to_env": "prod",
        "alias": "PG",
        "port_name": "db",
    }
    # try common shapes
    link, code = curl_json("POST", "/api/v1/links", token=token, body=link_body)
    print("POST /links HTTP", code, json.dumps(link, indent=2)[:800])

    links, code = curl_json("GET", "/api/v1/links", token=token)
    print("GET /links HTTP", code, json.dumps(links, indent=2)[:600])

    literals, code = curl_json("GET", "/api/v1/links/env-literals/lab-n8n/prod", token=token)
    print("env-literals HTTP", code, json.dumps(literals, indent=2)[:600])

    print("\n=== exposure sanity (DBs not public) ===")
    for host in (
        "https://lab-pg.softwarefactory.site",
        "https://lab-mongo.softwarefactory.site",
        "https://lab-api-bound.softwarefactory.site/health",
        "https://lab-react.softwarefactory.site/",
    ):
        rc, out = sh(f"curl -sS -o /dev/null -w '%{{http_code}}' --max-time 10 {host}")
        print(f"  {host} -> {out}")

    ok_mongo = any(l.startswith("MONGO_HOST=") for l in mongo_vars)
    print("\nMONGO_BINDINGS", "OK" if ok_mongo else "FAIL")
    return 0 if ok_mongo else 1


if __name__ == "__main__":
    sys.exit(main())
