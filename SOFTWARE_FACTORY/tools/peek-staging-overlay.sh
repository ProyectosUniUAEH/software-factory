#!/usr/bin/env bash
set -euo pipefail
# shellcheck disable=SC1091
set -a; source /tmp/kb-rebuild.env 2>/dev/null || true; set +a
tr -d '\r' </etc/kaanbal/installer.env >/tmp/kb-peek.env
set -a; # shellcheck disable=SC1091
source /tmp/kb-peek.env
set +a
ORG="${GITHUB_ORG:-${github_org:-}}"
TOKEN="${GITOPS_TOKEN:-${GITHUB_TOKEN:-${github_token:-}}}"
WORK=$(mktemp -d)
git clone --depth 1 "https://x-access-token:${TOKEN}@github.com/${ORG}/infra-gitops.git" "$WORK" >/dev/null 2>&1
OV="$WORK/apps/test-vue/overlays/staging"
echo "FILES:"
ls -la "$OV"
echo "==== kustomization.yaml ===="
cat "$OV/kustomization.yaml"
echo "==== other yaml ===="
for f in "$OV"/*.yaml; do
  echo "----- $(basename "$f") -----"
  cat "$f"
done
echo "==== DEV for compare ===="
ls "$WORK/apps/test-vue/overlays/dev"
