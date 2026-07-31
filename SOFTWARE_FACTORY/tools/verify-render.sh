#!/usr/bin/env bash
# Renderiza el baseline con las credenciales reales y comprueba, sobre el YAML ya
# compilado por kustomize, que sale exactamente lo que se espera: los hosts del
# engine, las imágenes del Docker Hub correcto, la ingressClass real y ni un solo
# placeholder o dominio heredado. No toca el cluster ni GitHub.
set -uo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${1:-/etc/kaanbal/installer.env}"
CLEAN="$(mktemp)"; OUT="$(mktemp -d)"; BUILT="$(mktemp)"
trap 'rm -rf "$CLEAN" "$OUT" "$BUILT"' EXIT
tr -d '\r' <"$ENV_FILE" >"$CLEAN"
# shellcheck disable=SC1090
set -a; . "$CLEAN"; set +a

DOMAIN="${domain:-${DOMAIN:-}}"
ORG="${github_org:-${GITHUB_ORG:-}}"
DUSER="${docker_user:-${DOCKER_USER:-}}"
EXPOSURE="${2:-public}"

G='\033[1;32m'; R='\033[1;31m'; N='\033[0m'
fails=0
check() { # check <descripción> <patrón-esperado>
  if grep -qE "$2" "$BUILT"; then printf "  ${G}OK${N}    %s\n" "$1"
  else printf "  ${R}FALLA${N} %s\n" "$1"; fails=$((fails+1)); fi
}
absent() { # absent <descripción> <patrón-prohibido>
  if grep -qE "$2" "$BUILT"; then
    printf "  ${R}FALLA${N} %s\n" "$1"; grep -nE "$2" "$BUILT" | head -3 | sed 's/^/          /'
    fails=$((fails+1))
  else printf "  ${G}OK${N}    %s\n" "$1"; fi
}

TS_ID="${tailscale_client_id:-${TAILSCALE_CLIENT_ID:-}}"
TS_ARGS=()
[[ -n "$TS_ID" ]] && TS_ARGS+=(--with-tailscale)

echo "Render: dominio=${DOMAIN} org=${ORG} docker=${DUSER} exposición=${EXPOSURE}" \
     "tailscale=$([[ -n "$TS_ID" ]] && echo sí || echo no)"
python3 "${SOURCE_DIR}/installer/gitops_render.py" \
  --src "${SOURCE_DIR}/infra-gitops" --out "$OUT" \
  --domain "$DOMAIN" --github-org "$ORG" --docker-user "$DUSER" \
  --api-tag prod-test123 --console-tag prod-test456 \
  --console-exposure "$EXPOSURE" --api-exposure "$EXPOSURE" \
  "${TS_ARGS[@]}" >/dev/null || exit 1

: >"$BUILT"
for overlay in "$OUT"/apps/*/overlays/prod; do
  [[ -d "$overlay" ]] || continue
  k3s kubectl kustomize "$overlay" >>"$BUILT" 2>/dev/null \
    || { printf "  ${R}FALLA${N} kustomize build de %s\n" "${overlay#$OUT/}"; fails=$((fails+1)); }
done
echo "  ($(wc -l <"$BUILT") líneas de YAML compilado)"

echo
echo "== Sin residuos de plantilla ni de instalaciones ajenas =="
absent "ningún \${KAANBAL_*} sin resolver" '\$\{KAANBAL_'
absent "ningún DOCKERHUB_USER literal"     'DOCKERHUB_USER'
absent "ningún dominio heredado"           'futurefarms\.mx|kaanbal-console\.local|REPLACE_AT_INSTALL'
absent "ninguna contraseña de ejemplo"     'CHANGEME|PLACEHOLDER'

echo
echo "== Imágenes =="
check "kaanbal-api apunta a ${DUSER}"     "image: ${DUSER}/kaanbal-api:prod-test123"
check "kaanbal-console apunta a ${DUSER}" "image: ${DUSER}/kaanbal-console:prod-test456"

echo
echo "== Exposición (${EXPOSURE}) =="
if [[ "$EXPOSURE" == "public" ]]; then
  check "consola en kaanbal-console"       "host: kaanbal-console\.${DOMAIN//./\\.}"
  check "atajo kaanbal"                    "host: kaanbal\.${DOMAIN//./\\.}"
  check "host de la API"                   "host: kaanbal-api\.${DOMAIN//./\\.}"
  check "host del agente"                  "host: kaanbal-agent\.${DOMAIN//./\\.}"
  check "ingressClass real del cluster"    "ingressClassName: traefik"
  absent "sin nginx heredado"              "ingressClassName: nginx"
  absent "sin TLS en cluster (lo hace Cloudflare)" "cert-manager\.io/cluster-issuer"
else
  absent "sin Ingress público" "kind: Ingress"
fi

echo
[[ $fails -eq 0 ]] && { printf "${G}Render verificado: %d comprobaciones, 0 fallas.${N}\n" 12; exit 0; }
printf "${R}Render con %d fallas.${N}\n" "$fails"; exit 1
