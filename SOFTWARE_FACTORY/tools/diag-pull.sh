#!/usr/bin/env bash
set -uo pipefail
K="sudo -n k3s kubectl"
CLEAN="$(mktemp)"; trap 'rm -f "$CLEAN"' EXIT
sudo -n cat /etc/kaanbal/installer.env | tr -d '\r' >"$CLEAN"
# shellcheck disable=SC1090
set -a; . "$CLEAN"; set +a
USER_NAME="${DOCKER_USER:-${docker_user:-}}"
TOKEN="${DOCKER_TOKEN:-${docker_token:-}}"

echo "=== PODS ==="
$K -n prod get pods

echo
echo "=== IMAGEN QUE PIDE CADA DEPLOYMENT ==="
$K -n prod get deploy -o jsonpath='{range .items[*]}{.metadata.name}{"  "}{.spec.template.spec.containers[0].image}{"\n"}{end}'

echo
echo "=== MOTIVO DEL FALLO ==="
$K -n prod get events --sort-by=.lastTimestamp | grep -iE "fail|error|backoff" | tail -8

echo
echo "=== TAGS PUBLICADOS EN DOCKER HUB ==="
hub="$(curl -sS -H 'Content-Type: application/json' \
  -d "{\"username\":\"${USER_NAME}\",\"password\":\"${TOKEN}\"}" \
  https://hub.docker.com/v2/users/login/ | python3 -c 'import sys,json; print(json.load(sys.stdin).get("token",""))')"
for repo in kaanbal-api kaanbal-console kaanbal-agent; do
  echo "  ${repo}:"
  curl -sS -H "Authorization: JWT ${hub}" \
    "https://hub.docker.com/v2/repositories/${USER_NAME}/${repo}/tags?page_size=10" \
    | python3 -c '
import sys, json
d = json.load(sys.stdin)
if d.get("message"):
    print("    ", d["message"]); raise SystemExit
for t in d.get("results", []):
    print("     %-24s %s" % (t.get("name"), t.get("last_updated", "")[:19]))'
done
