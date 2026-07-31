#!/usr/bin/env bash
# Reproduce exactamente la operación que falló: iniciar una subida de blob al
# registro. Es la primera escritura real que hace Kaniko.
set -uo pipefail
CLEAN="$(mktemp)"; trap 'rm -f "$CLEAN"' EXIT
sudo -n cat /etc/kaanbal/installer.env | tr -d '\r' >"$CLEAN"
# shellcheck disable=SC1090
set -a; . "$CLEAN"; set +a
USER_NAME="${DOCKER_USER:-${docker_user:-}}"
TOKEN="${DOCKER_TOKEN:-${docker_token:-}}"
REPO="${1:-kaanbal-api}"

echo "Pidiendo token de push para ${USER_NAME}/${REPO}..."
JWT="$(curl -sS -u "${USER_NAME}:${TOKEN}" \
  "https://auth.docker.io/token?service=registry.docker.io&scope=repository:${USER_NAME}/${REPO}:pull,push" \
  | python3 -c 'import sys,json; print(json.load(sys.stdin).get("token",""))')"
[[ -n "$JWT" ]] || { echo "No obtuve token"; exit 1; }
echo "  token obtenido (${#JWT} caracteres)"

echo
echo "Iniciando subida de blob (POST /v2/${USER_NAME}/${REPO}/blobs/uploads/)..."
curl -sS -o /dev/null -D - -X POST \
  -H "Authorization: Bearer ${JWT}" \
  "https://registry-1.docker.io/v2/${USER_NAME}/${REPO}/blobs/uploads/" \
  | head -12
