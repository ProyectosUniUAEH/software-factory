#!/usr/bin/env bash
# Inspecciona un repo remoto candidato a ser la consola de despliegue.
set -uo pipefail
REPO="${1:-futurefarms-softwarefactory/kaanbal-console}"
CLEAN="$(mktemp)"; DIR="$(mktemp -d)"
trap 'rm -rf "$CLEAN" "$DIR"' EXIT
sudo -n cat /etc/kaanbal/installer.env | tr -d '\r' >"$CLEAN"
# shellcheck disable=SC1090
set -a; . "$CLEAN"; set +a
TOKEN="${GITOPS_TOKEN:-${github_token:-}}"

git clone -q "https://x-access-token:${TOKEN}@github.com/${REPO}.git" "$DIR/r" 2>&1 || {
  echo "No pude clonar $REPO"; exit 1; }

echo "=== $REPO ==="
git -C "$DIR/r" log --oneline -8 --date=short --format='%h %ad %s'
echo
echo "--- raíz ---"
ls -1 "$DIR/r"
echo
echo "--- título del index ---"
grep -h '<title>' "$DIR/r/index.html" 2>/dev/null || echo "(sin index.html en raíz)"
echo
echo "--- ¿consume /api/v1/apps? ---"
grep -rl 'api/v1/apps' "$DIR/r" --include='*.vue' --include='*.js' --include='*.ts' 2>/dev/null | sed "s|$DIR/r/|  |" || true
echo "  (coincidencias: $(grep -r 'api/v1/apps' "$DIR/r" --include='*.vue' --include='*.js' --include='*.ts' 2>/dev/null | wc -l))"
echo
echo "--- vistas / componentes ---"
find "$DIR/r/src" -name '*.vue' 2>/dev/null | sed "s|$DIR/r/|  |" | head -40
echo
echo "--- rutas del router ---"
grep -rhE "path:\s*['\"]/" "$DIR/r/src" 2>/dev/null | head -25
