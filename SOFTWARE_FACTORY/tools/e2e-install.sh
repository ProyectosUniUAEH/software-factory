#!/usr/bin/env bash
# Instalación de extremo a extremo sin navegador: reset total, arranque del
# instalador y disparo de /api/install, siguiendo los pasos hasta el veredicto.
#
# Existe para poder validar el bootstrap completo de forma repetible; el asistente
# web hace exactamente lo mismo, solo que con un humano pulsando el botón.
#
#   sudo bash tools/e2e-install.sh <ruta-al-env> [public|tailnet]
set -uo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_SOURCE="${1:?uso: e2e-install.sh <ruta-al-env> [public|tailnet]}"
EXPOSURE="${2:-public}"
PORT=3000
if [[ "$EXPOSURE" == "public" ]]; then
  INSTALL_MODE="cloud"
elif [[ "$EXPOSURE" == "tailnet" ]]; then
  INSTALL_MODE="local"
else
  echo "Exposición inválida: ${EXPOSURE}. Usa public o tailnet." >&2
  exit 2
fi

C='\033[1;36m'; G='\033[1;32m'; R='\033[1;31m'; Y='\033[1;33m'; N='\033[0m'
say()  { printf "${C}[e2e]${N} %s\n" "$*"; }
good() { printf "${G}[e2e]${N} %s\n" "$*"; }
bad()  { printf "${R}[e2e]${N} %s\n" "$*"; }

ADMIN_PASS="${KAANBAL_ADMIN_PASS:-}"
if [[ -z "$ADMIN_PASS" ]]; then
  ADMIN_PASS="$(python3 -c 'import secrets; print("Kb-" + secrets.token_urlsafe(14))')"
fi

say "Reset total + arranque del instalador (exposición: ${EXPOSURE})"
bash "${SOURCE_DIR}/install.sh" --reset-local --reset-remote --preserve-credentials \
  --env "$ENV_SOURCE" || { bad "install.sh falló"; exit 1; }

TOKEN="$(cat /run/kaanbal-installer/token)"
BASE="http://127.0.0.1:${PORT}"
api() { curl -sS -H "X-Kaanbal-Token: ${TOKEN}" "$@"; }

for _ in $(seq 1 60); do
  api "${BASE}/api/state" >/dev/null 2>&1 && break
  sleep 1
done

say "Disparando la instalación"
api -X POST -H 'Content-Type: application/json' \
  -d "{\"admin_pass\":\"${ADMIN_PASS}\",\"mode\":\"${INSTALL_MODE}\",\"console_exposure\":\"${EXPOSURE}\",\"api_exposure\":\"${EXPOSURE}\"}" \
  "${BASE}/api/install" | python3 -c 'import sys,json; print("  ", json.load(sys.stdin))'

say "Siguiendo los pasos (esto tarda: se construyen las imágenes en el cluster)"
LAST=""
DEADLINE=$(( $(date +%s) + 3600 ))
while :; do
  snapshot="$(api "${BASE}/api/state" 2>/dev/null)"
  [[ -z "$snapshot" ]] && { sleep 5; continue; }

  line="$(printf '%s' "$snapshot" | python3 -c '
import sys, json
try:
    s = json.load(sys.stdin)
except Exception:
    raise SystemExit
steps = s.get("steps") or {}
order = ["preflight","k3s","argocd","gitops","tunel","repos","imagenes","plataforma","acceso"]
shown = []
for k in order:
    st = steps.get(k)
    if not st:
        continue
    mark = {"done":"OK","error":"XX","running":"..","pending":"--"}.get(st.get("status"), "??")
    shown.append("%s:%s" % (k, mark))
print("%s | %s" % (s.get("phase"), " ".join(shown)))')"

  if [[ "$line" != "$LAST" && -n "$line" ]]; then
    printf '  %s\n' "$line"
    LAST="$line"
  fi

  phase="${line%% *}"
  [[ "$phase" == "done" || "$phase" == "error" ]] && break
  (( $(date +%s) > DEADLINE )) && { bad "Tiempo agotado"; break; }
  sleep 6
done

echo
say "Bitácora de los pasos nuevos"
api "${BASE}/api/state" | python3 -c '
import sys, json
s = json.load(sys.stdin)
for entry in (s.get("log") or [])[-60:]:
    print("   %-5s %s" % (entry.get("level",""), entry.get("message","")))
'

echo
say "Resultado"
api "${BASE}/api/state" | python3 -c '
import sys, json
s = json.load(sys.stdin)
h = s.get("handoff") or {}
print("   fase:            ", s.get("phase"))
for k in ("domain", "console_url", "api_url", "argocd_url", "console_exposure",
          "console_reachable", "tunnel_live"):
    if k in h:
        print("   %-16s %s" % (k + ":", h[k]))
for k, st in (s.get("steps") or {}).items():
    if st.get("status") == "error":
        print("   ERROR en %s: %s" % (k, st.get("detail")))
'
printf "${Y}[e2e]${N} contraseña admin usada: %s\n" "$ADMIN_PASS"
