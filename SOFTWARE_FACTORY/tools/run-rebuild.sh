#!/usr/bin/env bash
set -euo pipefail
ROOT=/home/andres/kaanbal-next
export KAANBAL_ROOT="$ROOT"
mkdir -p "$ROOT/logs"
# Strip CR into tools/ so dirname still resolves to kaanbal-next
tr -d '\r' < "$ROOT/tools/rebuild-platform.sh" > "$ROOT/tools/rebuild-platform.run.sh"
chmod +x "$ROOT/tools/rebuild-platform.run.sh"
exec bash "$ROOT/tools/rebuild-platform.run.sh" "$@"
