#!/usr/bin/env bash
# Chequeo previo a una instalación desde cero: confirma que las credenciales del
# .env alcanzan para todo lo que el instalador va a intentar hacer por su cuenta.
# Se ejecuta solo; no modifica nada.
set -uo pipefail

ENV_FILE="${1:-/etc/kaanbal/installer.env}"
[[ -f "$ENV_FILE" ]] || { echo "No existe $ENV_FILE"; exit 1; }

# Se lee una copia sin CRLF: si el archivo viene de Windows, cada valor
# arrastraría un \r que rompe tokens y URLs sin dar ninguna pista.
CLEAN_ENV="$(mktemp)"
trap 'rm -f "$CLEAN_ENV"' EXIT
tr -d '\r' <"$ENV_FILE" >"$CLEAN_ENV"
# shellcheck disable=SC1090
set -a; . "$CLEAN_ENV"; set +a

norm() { # primer valor no vacío entre los alias de una credencial
  for name in "$@"; do
    local value="${!name:-}"
    [[ -n "$value" ]] && { printf '%s' "$value"; return; }
  done
}

ORG="$(norm github_org GITHUB_ORG KB_GIT_ORG)"
TOKEN="$(norm github_token GITHUB_TOKEN GITOPS_TOKEN KB_GIT_TOKEN)"
DUSER="$(norm docker_user DOCKER_USER DOCKERHUB_USER)"
DTOKEN="$(norm docker_token DOCKER_TOKEN DOCKERHUB_TOKEN)"
DOMAIN="$(norm domain DOMAIN KB_DOMAIN)"

fail=0
say()  { printf '  %s\n' "$*"; }
bad()  { printf '  \033[1;31mFALTA\033[0m %s\n' "$*"; fail=1; }
good() { printf '  \033[1;32mOK\033[0m    %s\n' "$*"; }

echo "== Credenciales =="
[[ -n "$DOMAIN" ]] && good "dominio: $DOMAIN"            || bad "dominio"
[[ -n "$ORG"    ]] && good "org GitHub: $ORG"            || bad "org de GitHub"
[[ -n "$TOKEN"  ]] && good "token de GitHub presente"    || bad "token de GitHub"
[[ -n "$DUSER"  ]] && good "usuario Docker Hub: $DUSER"  || bad "usuario de Docker Hub"
[[ -n "$DTOKEN" ]] && good "token de Docker Hub presente" || bad "token de Docker Hub"
[[ $fail -eq 0 ]] || { echo; echo "Completa el .env antes de instalar."; exit 1; }

echo
echo "== Scopes del token de GitHub =="
scopes="$(curl -sSI -H "Authorization: Bearer $TOKEN" https://api.github.com/user \
          | tr -d '\r' | awk -F': ' 'tolower($1)=="x-oauth-scopes"{print $2}')"
if [[ -z "$scopes" ]]; then
  say "token de grano fino (no reporta scopes clásicos); se validará por permisos efectivos"
else
  say "scopes: $scopes"
  for needed in repo workflow delete_repo; do
    if grep -qw "$needed" <<<"$scopes"; then good "$needed"
    elif [[ "$needed" == delete_repo ]]; then
      printf '  \033[1;33mAVISO\033[0m delete_repo ausente: --reset-remote no podrá borrar repos\n'
    else bad "$needed (necesario para publicar los repos core y sus workflows)"
    fi
  done
fi

echo
echo "== Repos core en $ORG =="
for r in infra-gitops kaanbal-api kaanbal-console kaanbal-templates; do
  curl -sS -H "Authorization: Bearer $TOKEN" "https://api.github.com/repos/$ORG/$r" \
    | python3 -c 'import sys,json
d=json.load(sys.stdin)
print("  %-20s %s" % (d.get("full_name") or "(no existe)",
      "" if "full_name" not in d else "private=%s branch=%s" % (d["private"], d["default_branch"])))'
done

echo
echo "== Docker Hub =="
tok="$(curl -sS -H 'Content-Type: application/json' \
       -d "{\"username\":\"$DUSER\",\"password\":\"$DTOKEN\"}" \
       https://hub.docker.com/v2/users/login/ \
       | python3 -c 'import sys,json; print(json.load(sys.stdin).get("token",""))' 2>/dev/null)"
[[ -n "$tok" ]] && good "login correcto como $DUSER" || bad "el token de Docker Hub no autentica"

echo
echo "== Cluster =="
if command -v k3s >/dev/null 2>&1; then
  k3s kubectl get ingressclass --no-headers 2>/dev/null \
    | awk '{print "  ingressclass: " $1 "  (" $2 ")"}' || say "sin ingressclass todavía"
  k3s kubectl -n prod get secret regcred >/dev/null 2>&1 \
    && good "secret regcred presente en prod" || say "regcred aún no existe (lo crea el instalador)"
else
  say "k3s no instalado todavía"
fi

echo
[[ $fail -eq 0 ]] && echo "Preflight OK." || echo "Preflight con faltantes."
exit $fail
