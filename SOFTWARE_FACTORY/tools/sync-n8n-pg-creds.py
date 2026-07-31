#!/usr/bin/env python3
"""Sync real lab-pg credentials into lab-n8n secrets (DB_POSTGRESDB_*)."""
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


def get_secret_data(ns, name_substr):
    secrets = sh(f"k3s kubectl -n {ns} get secrets -o name")
    for line in secrets.splitlines():
        if name_substr in line:
            name = line.strip()
            raw = subprocess.check_output(
                ["k3s", "kubectl", "-n", ns, "get", name, "-o", "json"], text=True
            )
            data = json.loads(raw)["data"]
            return name.split("/", 1)[-1], {
                k: base64.b64decode(v).decode() for k, v in data.items()
            }
    return None, {}


for ns in ("prod", "dev", "staging"):
    print(f"\n======== {ns} ========")
    pg_name, pg = get_secret_data(ns, "lab-pg-secrets")
    n8n_name, n8n = get_secret_data(ns, "lab-n8n-secrets")
    print("pg keys", list(pg))
    print("pg user", pg.get("POSTGRES_USER"), "db", pg.get("POSTGRES_DB"))
    print("n8n old user", n8n.get("DB_USER"), "host", n8n.get("DB_HOST"))

    user = pg.get("POSTGRES_USER") or "postgres"
    password = pg.get("POSTGRES_PASSWORD") or ""
    db = pg.get("POSTGRES_DB") or f"lab_pg"
    host = f"lab-pg.{ns}.svc.cluster.local"
    port = "5432"

    # Verify login
    sh(
        f"k3s kubectl -n {ns} exec lab-pg-0 -- "
        f"bash -c 'PGPASSWORD={password} psql -U {user} -d {db} -c \"SELECT 1\"'"
    )

    n8n.update(
        {
            "DB_HOST": host,
            "DB_PORT": port,
            "DB_DATABASE": db,
            "DB_USER": user,
            "DB_PASSWORD": password,
            "DB_URI": f"postgresql://{user}:{password}@{host}:{port}/{db}",
            "DB_TYPE": "postgresdb",
            "DB_POSTGRESDB_HOST": host,
            "DB_POSTGRESDB_PORT": port,
            "DB_POSTGRESDB_DATABASE": db,
            "DB_POSTGRESDB_USER": user,
            "DB_POSTGRESDB_PASSWORD": password,
        }
    )
    b64 = {k: base64.b64encode(v.encode()).decode() for k, v in n8n.items()}
    path = f"/tmp/n8n-sync-{ns}.json"
    with open(path, "w") as f:
        json.dump({"data": b64}, f)
    sh(f"k3s kubectl -n {ns} patch secret {n8n_name} --type merge --patch-file {path}")
    # Also wipe PVC again to avoid encryption mismatch after restarts
    sh(f"k3s kubectl -n {ns} delete sts lab-n8n --cascade=orphan --wait=false")
    time.sleep(2)
    sh(f"k3s kubectl -n {ns} delete pvc data-lab-n8n-0 --wait=false")
    time.sleep(2)
    sh(f"k3s kubectl -n {ns} delete pod lab-n8n-0 --force --grace-period=0")

print("\nwait recreate...")
time.sleep(45)
sh("k3s kubectl get pods -A | grep n8n")
sh("k3s kubectl -n prod logs lab-n8n-0 --tail=20")
sh("curl -sS -o /dev/null -w 'n8n=%{http_code}\\n' --max-time 25 https://lab-n8n.softwarefactory.site/")
print("SYNC_DONE")
