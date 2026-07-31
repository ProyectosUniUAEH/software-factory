#!/usr/bin/env python3
import base64
import json
import subprocess


def get_pg(ns):
    secs = subprocess.check_output(
        ["k3s", "kubectl", "-n", ns, "get", "secrets", "-o", "name"], text=True
    )
    name = [l for l in secs.splitlines() if "lab-pg-secrets" in l][0].split("/", 1)[-1]
    data = json.loads(
        subprocess.check_output(
            ["k3s", "kubectl", "-n", ns, "get", "secret", name, "-o", "json"], text=True
        )
    )["data"]
    return {k: base64.b64decode(v).decode() for k, v in data.items()}


pg = get_pg("prod")
user, password, db = pg["POSTGRES_USER"], pg["POSTGRES_PASSWORD"], pg["POSTGRES_DB"]
print("secret user", user, "db", db, "pass", password)

# TCP test from postgres pod itself (forces TCP with -h)
cmd = (
    f"k3s kubectl -n prod exec lab-pg-0 -- bash -c "
    f"\"PGPASSWORD='{password}' psql -h 127.0.0.1 -U {user} -d {db} -c 'SELECT current_user'\""
)
print(subprocess.run(cmd, shell=True, text=True, capture_output=True).stdout)
print(subprocess.run(cmd, shell=True, text=True, capture_output=True).stderr)

# show what n8n sees
n8n_secs = subprocess.check_output(
    ["k3s", "kubectl", "-n", "prod", "get", "secrets", "-o", "name"], text=True
)
n8n = [l for l in n8n_secs.splitlines() if "lab-n8n-secrets" in l][0].split("/", 1)[-1]
ndata = json.loads(
    subprocess.check_output(
        ["k3s", "kubectl", "-n", "prod", "get", "secret", n8n, "-o", "json"], text=True
    )
)["data"]
nd = {k: base64.b64decode(v).decode() for k, v in ndata.items()}
print("n8n DB_POSTGRESDB_USER", nd.get("DB_POSTGRESDB_USER"))
print("n8n DB_POSTGRESDB_PASSWORD", nd.get("DB_POSTGRESDB_PASSWORD"))
print("n8n DB_TYPE", nd.get("DB_TYPE"))
print("match", nd.get("DB_POSTGRESDB_PASSWORD") == password)

# Alter password to known value and update both secrets
new_pass = "LabN8nPgPass123!"
alter = (
    f"k3s kubectl -n prod exec lab-pg-0 -- bash -c "
    f"\"psql -U {user} -d {db} -c \\\"ALTER USER {user} WITH PASSWORD '{new_pass}';\\\"\""
)
print(subprocess.run(alter, shell=True, text=True, capture_output=True).stdout)
print(subprocess.run(alter, shell=True, text=True, capture_output=True).stderr)

# verify TCP
cmd2 = (
    f"k3s kubectl -n prod exec lab-pg-0 -- bash -c "
    f"\"PGPASSWORD='{new_pass}' psql -h 127.0.0.1 -U {user} -d {db} -c 'SELECT 1'\""
)
print("tcp verify", subprocess.run(cmd2, shell=True, text=True, capture_output=True).stdout)
print(subprocess.run(cmd2, shell=True, text=True, capture_output=True).stderr)

# patch n8n secret password fields
nd["DB_PASSWORD"] = new_pass
nd["DB_POSTGRESDB_PASSWORD"] = new_pass
nd["DB_URI"] = f"postgresql://{user}:{new_pass}@lab-pg.prod.svc.cluster.local:5432/{db}"
patch = {"data": {k: base64.b64encode(v.encode()).decode() for k, v in nd.items()}}
open("/tmp/n8n-newpass.json", "w").write(json.dumps(patch))
subprocess.run(
    f"k3s kubectl -n prod patch secret {n8n} --type merge --patch-file /tmp/n8n-newpass.json",
    shell=True,
)
subprocess.run(
    "k3s kubectl -n prod delete pod lab-n8n-0 --force --grace-period=0", shell=True
)
print("PASS_RESET_DONE")
