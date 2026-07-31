#!/usr/bin/env python3
"""Clear n8n DB state in postgres + check react rollout."""
import json
import subprocess
import time
from pathlib import Path


def sh(cmd):
    r = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    out = ((r.stdout or "") + (r.stderr or "")).strip()
    if out:
        print(out)
    return out


print("=== Drop n8n tables in lab-pg (prod/dev/staging) ===")
sql = r"""
DO $$ DECLARE r RECORD;
BEGIN
  FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname='public') LOOP
    EXECUTE 'DROP TABLE IF EXISTS public.' || quote_ident(r.tablename) || ' CASCADE';
  END LOOP;
END $$;
"""
# Safer: only drop if n8n settings exist
sql_n8n = (
    "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public; "
    "GRANT ALL ON SCHEMA public TO public; GRANT ALL ON SCHEMA public TO proadmin;"
)

for ns in ("prod", "dev", "staging"):
    print(f"-- {ns}")
    # get password from secret
    pw = sh(
        f"k3s kubectl -n {ns} get secret lab-pg-secrets -o jsonpath='{{.data.POSTGRES_PASSWORD}}' "
        f"| python3 -c 'import sys,base64; print(base64.b64decode(sys.stdin.read().strip()).decode())'"
    )
    # Actually secretGenerator keys may differ — try env from pod
    sh(
        f"k3s kubectl -n {ns} exec lab-pg-0 -- "
        f"bash -c \"psql -U proadmin -d lab_pg -c \\\"SELECT tablename FROM pg_tables WHERE schemaname='public' LIMIT 20;\\\"\""
    )

print("\n=== Try drop via n8n-related tables only ===")
for ns in ("prod", "dev"):
    sh(
        f"k3s kubectl -n {ns} exec lab-pg-0 -- "
        f"bash -c 'psql -U proadmin -d lab_pg -v ON_ERROR_STOP=0 <<EOF\n"
        f"DROP TABLE IF EXISTS settings CASCADE;\n"
        f"DROP TABLE IF EXISTS credentials_entity CASCADE;\n"
        f"DROP TABLE IF EXISTS workflow_entity CASCADE;\n"
        f"DROP TABLE IF EXISTS execution_entity CASCADE;\n"
        f"DROP TABLE IF EXISTS \"user\" CASCADE;\n"
        f"DROP TABLE IF EXISTS migrations CASCADE;\n"
        f"EOF'"
    )

print("\n=== Wipe n8n PVC again + restart ===")
for ns in ("prod", "dev"):
    sh(f"k3s kubectl -n {ns} delete pod lab-n8n-0 --force --grace-period=0")

time.sleep(25)
sh("k3s kubectl get pods -A | grep n8n")
sh("k3s kubectl -n prod logs lab-n8n-0 --tail=15 2>&1 || true")

print("\n=== react status ===")
sh("k3s kubectl -n argocd get applications | grep react || echo no-argo-react")
sh("k3s kubectl get pods -A | grep react || echo no-react-pods")
cfg = {}
for line in Path("/etc/kaanbal/installer.env").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    cfg[k.strip()] = v.strip()
tok = json.loads(
    subprocess.check_output(
        [
            "curl", "-sS", "-X", "POST",
            "https://kaanbal-api.softwarefactory.site/api/v1/auth/token",
            "--data-urlencode", f"username={cfg['KAANBAL_ADMIN_USER']}",
            "--data-urlencode", f"password={cfg['KAANBAL_ADMIN_PASS']}",
        ],
        text=True,
    )
)["access_token"]
st = subprocess.check_output(
    [
        "curl", "-sS", "-H", f"Authorization: Bearer {tok}",
        "https://kaanbal-api.softwarefactory.site/api/v1/apps/lab-react/status/full",
    ],
    text=True,
)
print(st[:1500])
print("N8N_DB_FIX_DONE")
