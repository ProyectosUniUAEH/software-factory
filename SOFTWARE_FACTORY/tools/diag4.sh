#!/usr/bin/env bash
set -uo pipefail
CLEAN="$(mktemp)"; DIR="$(mktemp -d)"
trap 'rm -rf "$CLEAN" "$DIR"' EXIT
# La redirección de entrada la hace el shell, no sudo: hay que leer con cat.
sudo -n cat /etc/kaanbal/installer.env | tr -d '\r' >"$CLEAN"
# shellcheck disable=SC1090
set -a; . "$CLEAN"; set +a
ORG="${GITHUB_ORG:-${github_org:-}}"
TOKEN="${GITOPS_TOKEN:-${github_token:-}}"

git clone --depth 1 -q \
  "https://x-access-token:${TOKEN}@github.com/${ORG}/infra-gitops.git" "$DIR/repo" 2>&1

echo "=== HEAD publicado ==="
git -C "$DIR/repo" log -1 --format='%h %ad %s' --date=short

echo
echo "=== apps/vault/base ==="
ls -1 "$DIR/repo/apps/vault/base" 2>&1

echo
echo "=== kustomization de vault ==="
cat "$DIR/repo/apps/vault/base/kustomization.yaml" 2>&1

echo
echo "=== ¿existe apps/tailscale-operator? ==="
ls -1 "$DIR/repo/apps/" 2>&1

echo
echo "=== ¿app-of-apps declara tailscale? ==="
grep -c 'name: tailscale-operator' "$DIR/repo/argocd/bootstrap/app-of-apps.yaml" 2>&1
