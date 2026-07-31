#!/usr/bin/env python3
"""Verify DB bindings on lab-api-bound and optionally recreate with bindings."""
import json
import subprocess
import sys

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


def sh(cmd):
    r = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def main():
    cfg = load_env()
    tok = curl_json(
        "POST", "/api/v1/auth/token",
        form={"username": cfg["KAANBAL_ADMIN_USER"], "password": cfg["KAANBAL_ADMIN_PASS"]},
    )["access_token"]

    print("=== secrets in prod ===")
    rc, out, _ = sh("k3s kubectl -n prod get secrets --no-headers")
    for line in out.splitlines():
        if "lab-api" in line or "lab-pg" in line or "lab-n8n" in line or "lab-mongo" in line:
            print(" ", line)

    print("\n=== lab-api-bound pod env (DB_*) ===")
    rc, out, err = sh("k3s kubectl -n prod exec deploy/lab-api-bound -- env")
    db_vars = [l for l in out.splitlines() if l.startswith("DB_")]
    print("\n".join(db_vars) if db_vars else "  (none)")

    print("\n=== vault lab-api-bound / lab-pg ===")
    for app in ("lab-api-bound", "lab-pg", "lab-mongo", "lab-n8n", "lab-emqx"):
        try:
            sec = curl_json("GET", f"/api/v1/system/vault/secrets/prod/{app}", token=tok)
            data = sec.get("data") or sec.get("secrets") or sec
            keys = list(data.keys()) if isinstance(data, dict) else data
            print(f"  prod/{app}: {keys}")
        except Exception as exc:
            print(f"  prod/{app}: ERROR {exc}")

    print("\n=== app docs bindings ===")
    for app in ("lab-api-bound", "lab-n8n"):
        try:
            doc = curl_json("GET", f"/api/v1/apps/{app}", token=tok)
            print(f"  {app}: template={doc.get('template')} bindings={doc.get('database_bindings')}")
        except Exception as exc:
            print(f"  {app}: {exc}")

    # If no DB_ env, delete and redeploy with bindings
    if not db_vars:
        print("\n=== REDEPLOY lab-api-bound WITH postgres binding ===")
        try:
            curl_json("DELETE", "/api/v1/apps/lab-api-bound", token=tok)
            print("deleted lab-api-bound")
        except Exception as exc:
            print("delete warn:", exc)
            # force delete via apps id if needed
            apps = curl_json("GET", "/api/v1/apps", token=tok)
            items = apps if isinstance(apps, list) else apps.get("apps") or apps.get("items") or []
            for a in items:
                if a.get("name") == "lab-api-bound":
                    aid = a.get("id") or a.get("_id")
                    print("found id", aid)
                    if aid:
                        curl_json("DELETE", f"/api/v1/apps/{aid}", token=tok)

        import time
        time.sleep(5)
        payload = {
            "name": "lab-api-bound",
            "template": "fastapi-api",
            "category": "backend",
            "environments": ["dev", "prod"],
            "creation_mode": "scaffold",
            "exposure": {
                "type": "public",
                "per_env": {"prod": "public", "dev": "tailscale"},
            },
            "database_bindings": {
                "prod": [{"app_name": "lab-pg", "env": "prod", "alias": "DB", "template": "postgres"}],
                "dev": [{"app_name": "lab-pg", "env": "dev", "alias": "DB", "template": "postgres"}],
            },
        }
        resp = curl_json("POST", "/api/v1/apps", token=tok, body=payload)
        print("redeploy:", resp)
        print("Waiting 3 min for build/rollout...")
        for i in range(24):
            time.sleep(15)
            rc, out, _ = sh("k3s kubectl -n prod get deploy lab-api-bound -o jsonpath='{.status.readyReplicas}'")
            print(f"  readyReplicas={out}")
            if out == "1":
                break
        rc, out, _ = sh("k3s kubectl -n prod exec deploy/lab-api-bound -- env")
        db_vars = [l for l in out.splitlines() if l.startswith("DB_")]
        print("DB_* after redeploy:")
        # redact password values
        for line in db_vars:
            k, _, v = line.partition("=")
            if "PASSWORD" in k or "URI" in k:
                print(f"  {k}=***")
            else:
                print(f"  {line}")
        print("BINDINGS_OK" if db_vars else "BINDINGS_MISSING")
        return 0 if db_vars else 1

    print("BINDINGS_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
