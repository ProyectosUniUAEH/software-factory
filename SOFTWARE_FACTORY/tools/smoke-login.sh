#!/usr/bin/env bash
# Prueba de humo de una célula viva: login real contra la API pública y lectura
# de la configuración que el instalador sembró. Solo lectura.
set -uo pipefail

ENV_FILE="${1:-/etc/kaanbal/installer.env}"
CLEAN="$(mktemp)"; trap 'rm -f "$CLEAN"' EXIT
tr -d '\r' <"$ENV_FILE" >"$CLEAN"
# shellcheck disable=SC1090
set -a; . "$CLEAN"; set +a

DOMAIN="${domain:-${DOMAIN:-}}"

# Las credenciales admiten varios nombres: el .env que escribe el usuario usa
# `agente-*` (con guion, que bash no puede exportar) y el que reescribe el
# instalador usa `KAANBAL_ADMIN_*`.
field() {
  for name in "$@"; do
    local value
    value="$(grep -iE "^${name}=" "$CLEAN" | head -1 | cut -d= -f2- | tr -d "\"'")"
    [[ -n "$value" ]] && { printf '%s' "$value"; return; }
  done
}
USER_NAME="$(field 'agente-user' 'KAANBAL_ADMIN_USER')"
PASS="$(field 'agente-password' 'KAANBAL_ADMIN_PASS')"
[[ -n "$USER_NAME" ]] || USER_NAME="admin"

API="https://kaanbal-api.${DOMAIN}"
G='\033[1;32m'; R='\033[1;31m'; N='\033[0m'
pass() { printf "  ${G}OK${N}    %s\n" "$*"; }
fail() { printf "  ${R}FALLA${N} %s\n" "$*"; }

echo "== Salud de la API =="
health="$(curl -sS --max-time 20 "${API}/health")"
[[ -n "$health" ]] && pass "health: $health" || fail "sin respuesta de ${API}/health"

echo
echo "== Login como ${USER_NAME} =="
# El endpoint es OAuth2 password flow: espera un formulario, no JSON.
resp="$(curl -sS --max-time 25 -X POST "${API}/api/v1/auth/token" \
        --data-urlencode "username=${USER_NAME}" \
        --data-urlencode "password=${PASS}")"
token="$(printf '%s' "$resp" | python3 -c 'import sys,json
try:
    d = json.load(sys.stdin)
except Exception:
    raise SystemExit
print(d.get("access_token") or d.get("token") or "")' 2>/dev/null)"

if [[ -n "$token" ]]; then
  pass "login correcto, token emitido"
else
  fail "login rechazado: $(printf '%s' "$resp" | head -c 200)"
fi

echo
echo "== Configuración sembrada =="
if [[ -n "$token" ]]; then
  curl -sS --max-time 20 "${API}/api/v1/setup/status" \
    -H "Authorization: Bearer ${token}" \
    | python3 -c 'import sys,json
try:
    d = json.load(sys.stdin)
except Exception:
    print("  (respuesta no JSON)"); raise SystemExit
for k in sorted(d):
    print("  %-24s %s" % (k + ":", d[k]))' 2>/dev/null || echo "  (endpoint no disponible)"
else
  echo "  (omitido: sin token)"
fi
