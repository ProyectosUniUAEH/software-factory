"""
Seed MongoDB apps collection from ArgoCD.
Run this inside the kaanbal-api pod:
  kubectl exec -n prod <kaanbal-api-pod> -- python3 /tmp/seed_apps_mongodb.py
"""
import urllib.request, urllib.error, urllib.parse, json, ssl
from datetime import datetime

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

BASE_API = "http://localhost:8000"
ARGOCD = "https://argocd-server.argocd.svc.cluster.local"
ARGOCD_PASS = "g8x6vWxGtmfuMt9x"
KB_USER = "admin"
KB_PASS = "Admin2026!"

def api_call(method, path, data=None, token=None, form=False):
    url = BASE_API + path
    if form and data:
        body = urllib.parse.urlencode(data).encode()
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
    else:
        body = json.dumps(data).encode() if data else None
        headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": e.code, "body": e.read().decode()}

def argo_call(path, token):
    req = urllib.request.Request(ARGOCD + path,
        headers={"Authorization": "Bearer " + token})
    resp = urllib.request.urlopen(req, context=ctx, timeout=15)
    return json.loads(resp.read().decode())

# === Login Kaanbal ===
kb_resp = api_call("POST", "/api/v1/auth/token",
    data={"username": KB_USER, "password": KB_PASS}, form=True)
token = kb_resp["access_token"]
print(f"[+] Kaanbal login OK")

# === Login ArgoCD ===
argo_req = urllib.request.Request(ARGOCD + "/api/v1/session",
    data=json.dumps({"username": "admin", "password": ARGOCD_PASS}).encode(),
    headers={"Content-Type": "application/json"}, method="POST")
argo_resp = urllib.request.urlopen(argo_req, context=ctx, timeout=15)
argo_token = json.loads(argo_resp.read().decode())["token"]
print(f"[+] ArgoCD login OK")

# === List ArgoCD Apps ===
argocd_apps = argo_call("/api/v1/applications", argo_token)["items"]
print(f"[+] ArgoCD apps: {len(argocd_apps)}")

# === Check existing MongoDB apps ===
mongo_apps = api_call("GET", "/api/v1/apps", token=token)
existing_names = {a["name"] for a in mongo_apps} if isinstance(mongo_apps, list) else set()
print(f"[+] MongoDB existing apps: {len(existing_names)}")

# === Skip infra/system apps ===
SKIP_PREFIXES = [
    "applicationsets", "core-config", "datastore-",
    "kaanbal-api-", "kaanbal-console-", "tailscale-operator",
    "vault-", "kaanbal-api", "kaanbal-console"
]

def should_skip(name):
    for p in SKIP_PREFIXES:
        if name == p.rstrip("-") or name.startswith(p):
            return True
    return False

# === Category + Template detection ===
def detect_category(name):
    checks = [
        (["vue", "console", "web-", "frontend", "ui-"], "frontend"),
        (["api-", "-api", "svc-", "-svc", "backend", "service"], "backend"),
        (["mongo", "mysql", "postgresql", "postgres", "redis", "db-", "-db"], "database"),
        (["broker", "emqx", "mqtt", "kafka", "rabbit"], "messaging"),
        (["n8n", "workflow", "automation"], "workflow"),
    ]
    for patterns, cat in checks:
        if any(p in name for p in patterns):
            return cat
    return "backend"

def detect_template(name):
    checks = [
        (["vue", "console"], "vue3-spa"),
        (["-api", "api-", "fastapi", "backend"], "fastapi-api"),
        (["mongo"], "mongodb"),
        (["mysql"], "mysql"),
        (["postgresql", "postgres"], "postgresql"),
        (["broker", "emqx"], "emqx"),
        (["n8n"], "n8n"),
    ]
    for patterns, tpl in checks:
        if any(p in name for p in patterns):
            return tpl
    return "fastapi-api"

# === Deduplicate by base name (strip env suffix) ===
seen_bases = set(existing_names)
seeded = 0
skipped = 0

for app in argocd_apps:
    name = app["metadata"]["name"]

    if should_skip(name):
        print(f"  [skip-infra] {name}")
        continue

    # Strip env suffix
    parts = name.rsplit("-", 1)
    if len(parts) == 2 and parts[1] in ["prod", "staging", "dev"]:
        base_name = parts[0]
    else:
        base_name = name

    if base_name in seen_bases:
        print(f"  [skip-dup]   {base_name}")
        continue

    seen_bases.add(base_name)

    health = app.get("status", {}).get("health", {}).get("status", "Unknown")
    sync = app.get("status", {}).get("sync", {}).get("status", "Unknown")

    category = detect_category(base_name)
    template = detect_template(base_name)
    now = datetime.utcnow().isoformat()

    doc = {
        "name": base_name,
        "template": template,
        "category": category,
        "description": f"Imported from ArgoCD",
        "environments": ["dev", "staging", "prod"],
        "creation_mode": "scaffold",
        "exposure": {"type": "internal"},
        "specs": {"replicas": 1, "port": 80},
        "status": "healthy" if health == "Healthy" else "deploying",
        "argocd_status": health,
        "argocd_sync_status": sync,
        "created_at": now,
        "updated_at": now,
    }

    print(f"  [seed] {base_name} ({category}/{template}, {health}/{sync})")
    result = api_call("POST", "/api/v1/apps", data=doc, token=token)

    if "error" in result:
        code = result.get("error")
        if code == 409:
            print(f"         Already exists (409), skipping")
        else:
            print(f"         ERROR {code}: {result.get('body','')[:100]}")
        skipped += 1
    else:
        seeded += 1

print(f"\n{'='*50}")
print(f"Seeded: {seeded}  |  Skipped: {skipped}")

final = api_call("GET", "/api/v1/apps", token=token)
print(f"MongoDB apps total: {len(final) if isinstance(final, list) else '?'}")
