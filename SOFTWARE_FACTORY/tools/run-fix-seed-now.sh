#!/usr/bin/env bash
set -euo pipefail
pkill -f wipe-and-redeploy-v1-mixed || true
bash /home/andres/kaanbal-next/tools/fix-platform-seed.sh
echo AFTER_SEED
