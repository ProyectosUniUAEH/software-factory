#!/usr/bin/env python3
"""
Wipe ALL user apps (keep Kaanbal core) then redeploy v1 stack with MIXED exposure.

Plan (orden lógico):
  1) Wipe: API delete → GitHub repos → Docker images → ArgoCD/k8s → Vault → Tailscale orphans
  2) DBs first (compartibles):
       lab-mongo, lab-pg
       prod=tailscale, staging=tailscale, dev=internal
  3) EMQX (complejo multi-port):
       prod=public (dashboard), staging=tailscale, dev=internal
  4) n8n (workflow) + binding a lab-pg:
       prod=public, staging=tailscale, dev=tailscale
       (workflow no permite internal)
  5) FastAPI bound a postgres (+ opcional mongo):
       prod=public, staging=tailscale, dev=internal
  6) React frontend:
       prod=public, staging=tailscale, dev=tailscale
       (frontend no permite internal)

Validaciones:
  - BD en dominio público → 404
  - Bindings DB_* / MONGO_* en pods
  - URLs prod públicas 200
  - Devices Tailscale para env VPN
"""
from __future__ import annotations

import json
import subprocess
import sys
import time

API = "https://kaanbal-api.softwarefactory.site"
CORE_PREFIXES = (
    "kaanbal-", "argocd", "vault", "cloudflared", "datastore",
    "tailscale", "infra",
)
# ArgoCD Application names that must NEVER be deleted during user wipe
PROTECTED_ARGOCD_APPS = {
    "applicationsets",
    "core-config",
    "vault",
    "tailscale-operator",
    "root",
    "app-of-apps",
}
PROTECTED_ARGOCD_PREFIXES = (
    "kaanbal-", "cloudflared", "datastore", "vault", "tailscale",
)


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


def sh(cmd, check=False):
    r = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    if check and r.returncode != 0:
        print(r.stderr or r.stdout, file=sys.stderr)
        raise SystemExit(r.returncode)
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
    body_s, code = out.rsplit("__HTTP__", 1) if "__HTTP__" in out else (out, "?")
    try:
        data = json.loads(body_s) if body_s.strip() else {}
    except json.JSONDecodeError:
        data = {"raw": body_s[:500]}
    return data, code.strip()


def auth(cfg):
    data, code = curl_json(
        "POST", "/api/v1/auth/token",
        form={"username": cfg["KAANBAL_ADMIN_USER"], "password": cfg["KAANBAL_ADMIN_PASS"]},
    )
    if code != "200":
        raise SystemExit(f"auth fail {code} {data}")
    return data["access_token"]


def list_apps(token):
    data, code = curl_json("GET", "/api/v1/apps", token=token)
    if code != "200":
        print("list apps fail", code, data)
        return []
    if isinstance(data, list):
        return data
    return data.get("apps") or data.get("items") or data.get("data") or []


def is_core(name: str) -> bool:
    n = (name or "").lower()
    return any(n.startswith(p) or n == p.rstrip("-") for p in CORE_PREFIXES)


def wipe_all(token):
    print("\n======== WIPE USER APPS ========")
    apps = list_apps(token)
    print(f"found {len(apps)} apps in API")
    for app in apps:
        name = app.get("name") or ""
        aid = str(app.get("id") or app.get("_id") or "")
        if is_core(name):
            print(f"  KEEP core {name}")
            continue
        if not aid:
            print(f"  SKIP no id {name}")
            continue
        print(f"  DELETE {name} ({aid})")
        data, code = curl_json("DELETE", f"/api/v1/apps/{aid}", token=token)
        print(f"    HTTP {code} cleanup={str(data.get('cleanup') or data.get('detail') or '')[:180]}")

    # Service links
    links, code = curl_json("GET", "/api/v1/links", token=token)
    if code == "200" and isinstance(links, list):
        for link in links:
            lid = link.get("_id") or link.get("id")
            if lid:
                curl_json("DELETE", f"/api/v1/links/{lid}", token=token)
                print(f"  DELETE link {lid}")

    # Orphan cleanup
    for path in (
        "/api/v1/apps/maintenance/cleanup-orphans?dry_run=false",
        "/api/v1/apps/maintenance/cleanup-tailscale?dry_run=false",
    ):
        data, code = curl_json("POST", path, token=token)
        print(f"  maintenance {path.split('/')[-1]} HTTP {code}")

    # Leftover ArgoCD apps (user ONLY — never platform)
    rc, out, _ = sh("k3s kubectl -n argocd get applications -o name")
    for line in out.splitlines():
        name = line.split("/")[-1]
        if name in PROTECTED_ARGOCD_APPS:
            print(f"  KEEP protected {name}")
            continue
        if any(name.startswith(p) for p in PROTECTED_ARGOCD_PREFIXES):
            print(f"  KEEP platform {name}")
            continue
        base = name.rsplit("-", 1)[0] if name.endswith(("-dev", "-prod", "-staging")) else name
        if is_core(base) or is_core(name) or base in PROTECTED_ARGOCD_APPS:
            print(f"  KEEP core {name}")
            continue
        # Only delete apps that look like user apps (lab-*, smoke, etc.)
        print(f"  kubectl delete application {name}")
        sh(f"k3s kubectl -n argocd delete application {name} --wait=false")

    print("WIPE_DONE")


def wait_ready(ns, app, tries=40):
    for i in range(tries):
        rc, out, _ = sh(
            f"k3s kubectl -n {ns} get deploy,sts -l app={app} "
            f"-o jsonpath='{{range .items[*]}}{{.status.readyReplicas}} {{end}}'"
        )
        ready = any(x.strip() not in ("", "0") for x in out.split())
        print(f"  wait {ns}/{app} i={i} ready={ready} raw={out!r}")
        if ready:
            return True
        time.sleep(15)
    return False


def deploy(token, payload):
    name = payload["name"]
    print(f"\n=== DEPLOY {name} ===")
    print(json.dumps({k: payload[k] for k in ("template", "environments", "exposure", "database_bindings") if k in payload}, indent=2))
    data, code = curl_json("POST", "/api/v1/apps", token=token, body=payload)
    print(f"HTTP {code}", json.dumps(data)[:300])
    ok = code.startswith("2")
    if not ok:
        print(f"DEPLOY_FAILED {name}")
    return ok


def http_code(url):
    rc, out, _ = sh(f"curl -sS -o /dev/null -w '%{{http_code}}' --max-time 15 '{url}'")
    return out


def main():
    cfg = load_env()
    token = auth(cfg)
    print("auth OK")

    only = sys.argv[1:]  # optional: wipe | deploy | all
    mode = only[0] if only else "all"

    if mode in ("wipe", "all"):
        wipe_all(token)
        if mode == "wipe":
            return 0
        print("\nSleep 20s after wipe...")
        time.sleep(20)

    # Refresh templates
    curl_json("GET", "/api/v1/templates/refresh", token=token)

    # ---- Phase 1: databases ----
    db_exposure = {
        "type": "tailscale",
        "per_env": {"prod": "tailscale", "staging": "tailscale", "dev": "internal"},
    }
    ok_m = deploy(token, {
        "name": "lab-mongo",
        "template": "mongodb",
        "category": "database",
        "environments": ["dev", "staging", "prod"],
        "creation_mode": "config-only",
        "exposure": db_exposure,
    })
    ok_p = deploy(token, {
        "name": "lab-pg",
        "template": "postgres",
        "category": "database",
        "environments": ["dev", "staging", "prod"],
        "creation_mode": "config-only",
        "exposure": db_exposure,
    })
    if not (ok_m and ok_p):
        print("ABORT: DB deploy failed — fix platform seed/domain and retry")
        return 2

    print("\nWaiting DBs...")
    time.sleep(25)
    ok_mongo = wait_ready("prod", "lab-mongo") and wait_ready("dev", "lab-mongo")
    ok_pg = wait_ready("prod", "lab-pg") and wait_ready("dev", "lab-pg")
    print(f"DBs mongo={ok_mongo} pg={ok_pg}")

    # ---- Phase 2: EMQX mixed ----
    deploy(token, {
        "name": "lab-emqx",
        "template": "emqx",
        "category": "iot",
        "environments": ["dev", "staging", "prod"],
        "creation_mode": "config-only",
        "exposure": {
            "type": "tailscale",
            "per_env": {"prod": "public", "staging": "tailscale", "dev": "internal"},
        },
    })

    # ---- Phase 3: n8n + postgres binding ----
    deploy(token, {
        "name": "lab-n8n",
        "template": "n8n",
        "category": "workflow",
        "environments": ["dev", "staging", "prod"],
        "creation_mode": "config-only",
        "exposure": {
            "type": "public",
            "per_env": {"prod": "public", "staging": "tailscale", "dev": "tailscale"},
        },
        "database_bindings": {
            "prod": [{"app_name": "lab-pg", "env": "prod", "alias": "DB", "template": "postgres"}],
            "staging": [{"app_name": "lab-pg", "env": "staging", "alias": "DB", "template": "postgres"}],
            "dev": [{"app_name": "lab-pg", "env": "dev", "alias": "DB", "template": "postgres"}],
        },
    })

    # ---- Phase 4: FastAPI bound to postgres (full mix) ----
    deploy(token, {
        "name": "lab-api",
        "template": "fastapi-api",
        "category": "backend",
        "environments": ["dev", "staging", "prod"],
        "creation_mode": "scaffold",
        "exposure": {
            "type": "public",
            "per_env": {"prod": "public", "staging": "tailscale", "dev": "internal"},
        },
        "database_bindings": {
            "prod": [
                {"app_name": "lab-pg", "env": "prod", "alias": "DB", "template": "postgres"},
                {"app_name": "lab-mongo", "env": "prod", "alias": "MONGO", "template": "mongodb"},
            ],
            "staging": [
                {"app_name": "lab-pg", "env": "staging", "alias": "DB", "template": "postgres"},
            ],
            "dev": [
                {"app_name": "lab-pg", "env": "dev", "alias": "DB", "template": "postgres"},
            ],
        },
    })

    # ---- Phase 5: React ----
    deploy(token, {
        "name": "lab-react",
        "template": "react-spa",
        "category": "frontend",
        "environments": ["dev", "staging", "prod"],
        "creation_mode": "scaffold",
        "exposure": {
            "type": "public",
            "per_env": {"prod": "public", "staging": "tailscale", "dev": "tailscale"},
        },
    })

    print("\n======== WAIT ROLLOUTS (scaffold builds take time) ========")
    time.sleep(60)
    results = {}
    for app, ns in (
        ("lab-emqx", "prod"),
        ("lab-n8n", "prod"),
        ("lab-api", "prod"),
        ("lab-react", "prod"),
        ("lab-api", "dev"),
        ("lab-mongo", "dev"),
    ):
        results[f"{ns}/{app}"] = wait_ready(ns, app)

    print("\n======== VALIDATION ========")
    checks = {
        "pg_public_blocked": http_code("https://lab-pg.softwarefactory.site") in ("404", "000", "503"),
        "mongo_public_blocked": http_code("https://lab-mongo.softwarefactory.site") in ("404", "000", "503"),
        "api_prod": http_code("https://lab-api.softwarefactory.site/health") == "200",
        "react_prod": http_code("https://lab-react.softwarefactory.site/") == "200",
        "n8n_prod": http_code("https://lab-n8n.softwarefactory.site/") in ("200", "301", "302", "401", "403"),
    }
    for k, v in checks.items():
        print(f"  {k}: {v}")

    # Binding check on lab-api prod
    rc, out, _ = sh("k3s kubectl -n prod exec deploy/lab-api -- env")
    db_ok = "DB_HOST=" in out and "lab-pg.prod.svc.cluster.local" in out
    mongo_ok = "MONGO_HOST=" in out and "lab-mongo.prod.svc.cluster.local" in out
    print(f"  api_db_binding: {db_ok}")
    print(f"  api_mongo_binding: {mongo_ok}")

    # n8n binding
    rc, out, _ = sh("k3s kubectl -n prod exec deploy/lab-n8n -- env 2>/dev/null || k3s kubectl -n prod exec sts/lab-n8n -- env")
    n8n_db = "DB_HOST=" in out and "lab-pg" in out
    print(f"  n8n_db_binding: {n8n_db}")

    print("\n======== TAILSCALE (sample) ========")
    sh("sudo python3 /tmp/list-ts-devices.py 2>/dev/null | grep -i lab- | head -40")

    print("\nRESULTS pods:", json.dumps(results, indent=2))
    all_ok = all(results.values()) and db_ok and checks["api_prod"] and checks["react_prod"]
    print("OVERALL", "OK" if all_ok else "PARTIAL")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
