#!/usr/bin/env python3
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


print("=== pod secret ref + logs ===")
sh("k3s kubectl -n prod get pod lab-n8n-0 -o yaml | sed -n '/envFrom:/,/image:/p' | head -20")
sh("k3s kubectl -n prod logs lab-n8n-0 --tail=25")

print("\n=== disable selfHeal ===")
patch = {
    "spec": {
        "syncPolicy": {
            "automated": {"selfHeal": False, "prune": True}
        }
    }
}
path = "/tmp/disable-selfheal.json"
open(path, "w").write(json.dumps(patch))
for app in ("lab-n8n-prod", "lab-n8n-dev", "lab-n8n-staging"):
    sh(f"k3s kubectl -n argocd patch application {app} --type merge --patch-file {path}")

for ns in ("prod", "dev", "staging"):
    print(f"\n===== fix {ns} =====")
    secs = sh(f"k3s kubectl -n {ns} get secrets -o name")
    pg = n8n = None
    for line in secs.splitlines():
        if "lab-pg-secrets" in line:
            pg = line.split("/", 1)[-1]
        if "lab-n8n-secrets" in line:
            n8n = line.split("/", 1)[-1]
    pg_d = {
        k: base64.b64decode(v).decode()
        for k, v in json.loads(
            subprocess.check_output(
                ["k3s", "kubectl", "-n", ns, "get", "secret", pg, "-o", "json"], text=True
            )
        )["data"].items()
    }
    n8n_d = {
        k: base64.b64decode(v).decode()
        for k, v in json.loads(
            subprocess.check_output(
                ["k3s", "kubectl", "-n", ns, "get", "secret", n8n, "-o", "json"], text=True
            )
        )["data"].items()
    }
    user = pg_d["POSTGRES_USER"]
    password = pg_d["POSTGRES_PASSWORD"]
    db = pg_d["POSTGRES_DB"]
    host = f"lab-pg.{ns}.svc.cluster.local"
    print(f"sync user={user} db={db} host={host} pass_len={len(password)}")
    n8n_d.update(
        {
            "DB_TYPE": "postgresdb",
            "DB_POSTGRESDB_HOST": host,
            "DB_POSTGRESDB_PORT": "5432",
            "DB_POSTGRESDB_DATABASE": db,
            "DB_POSTGRESDB_USER": user,
            "DB_POSTGRESDB_PASSWORD": password,
            "DB_HOST": host,
            "DB_PORT": "5432",
            "DB_DATABASE": db,
            "DB_USER": user,
            "DB_PASSWORD": password,
            "DB_URI": f"postgresql://{user}:{password}@{host}:5432/{db}",
            "DB_POSTGRESDB_SSL_ENABLED": "false",
        }
    )
    p = f"/tmp/fix-n8n-{ns}.json"
    open(p, "w").write(
        json.dumps({"data": {k: base64.b64encode(v.encode()).decode() for k, v in n8n_d.items()}})
    )
    sh(f"k3s kubectl -n {ns} patch secret {n8n} --type merge --patch-file {p}")
    sh(f"k3s kubectl -n {ns} delete pod lab-n8n-0 --force --grace-period=0")

print("\n=== TCP auth from lab-api ===")
sh(
    "k3s kubectl -n prod exec deploy/lab-api -- python -c \""
    "import os,socket;"
    "host=os.environ['DB_HOST']; port=int(os.environ['DB_PORT']);"
    "print('tcp', host, port);"
    "s=socket.create_connection((host,port),5); print('tcp-ok'); s.close()"
    "\""
)

# try psql over TCP from postgres pod itself
sh(
    "k3s kubectl -n prod get secret -o name | head"
)

time.sleep(45)
print("\n=== final ===")
sh("k3s kubectl get pods -A | grep n8n")
sh("k3s kubectl -n prod logs lab-n8n-0 --tail=35")
sh("curl -sS -o /dev/null -w 'n8n=%{http_code}\\n' --max-time 20 https://lab-n8n.softwarefactory.site/")
print("DONE")
