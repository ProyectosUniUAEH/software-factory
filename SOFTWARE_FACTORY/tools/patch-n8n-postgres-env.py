#!/usr/bin/env python3
"""Patch n8n secrets with DB_POSTGRESDB_* and restart."""
import base64
import json
import subprocess
import time


def sh(cmd):
    r = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    out = ((r.stdout or "") + (r.stderr or "")).strip()
    if out:
        print(out)
    return out


for ns in ("prod", "dev", "staging"):
    print(f"\n======== {ns} ========")
    secrets = sh(f"k3s kubectl -n {ns} get secrets -o name")
    sec = ""
    for line in secrets.splitlines():
        if "lab-n8n-secrets" in line:
            sec = line.strip()
            break
    if not sec:
        print("no secret")
        continue
    raw = subprocess.check_output(
        ["k3s", "kubectl", "-n", ns, "get", sec, "-o", "json"], text=True
    )
    data = json.loads(raw)["data"]
    decoded = {k: base64.b64decode(v).decode() for k, v in data.items()}
    print("keys", list(decoded))
    for k in sorted(decoded):
        val = decoded[k]
        if "PASS" in k or "KEY" in k or "URI" in k:
            print(f"  {k}=***")
        else:
            print(f"  {k}={val}")

    host = decoded.get("DB_HOST") or f"lab-pg.{ns}.svc.cluster.local"
    port = decoded.get("DB_PORT") or "5432"
    db = decoded.get("DB_DATABASE") or "lab_pg"
    user = decoded.get("DB_USER") or "proadmin"
    password = decoded.get("DB_PASSWORD") or ""

    patch = {
        "DB_TYPE": "postgresdb",
        "DB_POSTGRESDB_HOST": host,
        "DB_POSTGRESDB_PORT": str(port),
        "DB_POSTGRESDB_DATABASE": db,
        "DB_POSTGRESDB_USER": user,
        "DB_POSTGRESDB_PASSWORD": password,
        "N8N_DIAGNOSTICS_ENABLED": "false",
        "N8N_PERSONALIZATION_ENABLED": "false",
    }
    # merge into secret
    for k, v in patch.items():
        decoded[k] = v
    b64 = {k: base64.b64encode(v.encode()).decode() for k, v in decoded.items()}
    patch_body = {"data": b64}
    path = f"/tmp/n8n-sec-{ns}.json"
    with open(path, "w") as f:
        json.dump(patch_body, f)
    name = sec.split("/", 1)[-1]
    sh(f"k3s kubectl -n {ns} patch secret {name} --type merge --patch-file {path}")
    sh(f"k3s kubectl -n {ns} delete pod lab-n8n-0 --force --grace-period=0")

print("\nwaiting...")
time.sleep(35)
sh("k3s kubectl get pods -A | grep n8n")
sh("k3s kubectl -n prod logs lab-n8n-0 --tail=25")
sh("curl -sS -o /dev/null -w 'n8n=%{http_code}\\n' --max-time 20 https://lab-n8n.softwarefactory.site/")
print("N8N_PG_PATCH_DONE")
