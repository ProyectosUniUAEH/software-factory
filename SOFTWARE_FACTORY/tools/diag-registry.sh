#!/usr/bin/env bash
# ¿Sirven las credenciales de Docker Hub para EMPUJAR al registro?
# El login de hub.docker.com y el token del registro son cosas distintas: se
# puede autenticar en la web y aun así no tener permiso de push.
set -uo pipefail
CLEAN="$(mktemp)"; trap 'rm -f "$CLEAN"' EXIT
sudo -n cat /etc/kaanbal/installer.env | tr -d '\r' >"$CLEAN"
# shellcheck disable=SC1090
set -a; . "$CLEAN"; set +a
USER_NAME="${DOCKER_USER:-${docker_user:-}}"
TOKEN="${DOCKER_TOKEN:-${docker_token:-}}"
REPO="${1:-kaanbal-api}"

echo "=== Token del registro con permiso de push para ${USER_NAME}/${REPO} ==="
resp="$(curl -sS -u "${USER_NAME}:${TOKEN}" \
  "https://auth.docker.io/token?service=registry.docker.io&scope=repository:${USER_NAME}/${REPO}:pull,push")"
python3 -c '
import sys, json, base64
d = json.load(sys.stdin)
tok = d.get("token") or d.get("access_token") or ""
if not tok:
    print("  sin token:", str(d)[:200]); raise SystemExit
payload = tok.split(".")[1]
payload += "=" * (-len(payload) % 4)
claims = json.loads(base64.urlsafe_b64decode(payload))
access = claims.get("access") or []
if not access:
    print("  TOKEN EMITIDO PERO SIN PERMISOS: el registro no concede nada")
for a in access:
    print("  %s %s -> %s" % (a.get("type"), a.get("name"), ",".join(a.get("actions", []))))' <<<"$resp"

echo
echo "=== Secret regcred en el cluster ==="
sudo -n k3s kubectl -n prod get secret regcred -o jsonpath='{.data.\.dockerconfigjson}' 2>/dev/null \
  | base64 -d \
  | python3 -c '
import sys, json, base64
d = json.load(sys.stdin)
for host, entry in (d.get("auths") or {}).items():
    raw = base64.b64decode(entry.get("auth", "")).decode(errors="replace")
    user = raw.split(":", 1)[0] if ":" in raw else "?"
    secret = raw.split(":", 1)[1] if ":" in raw else ""
    print("  %s  usuario=%s  secreto=%d caracteres" % (host, user, len(secret)))'

echo
echo "=== Repos actuales en Docker Hub ==="
hub="$(curl -sS -H 'Content-Type: application/json' \
  -d "{\"username\":\"${USER_NAME}\",\"password\":\"${TOKEN}\"}" \
  https://hub.docker.com/v2/users/login/ | python3 -c 'import sys,json; print(json.load(sys.stdin).get("token",""))')"
curl -sS -H "Authorization: JWT ${hub}" \
  "https://hub.docker.com/v2/repositories/${USER_NAME}/?page_size=25" \
  | python3 -c '
import sys, json
d = json.load(sys.stdin)
print("  total:", d.get("count"))
for r in d.get("results", []):
    print("   ", r.get("name"))'
