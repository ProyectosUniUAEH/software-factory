#!/usr/bin/env bash
# Re-seed + deploy mixed v1 (no wipe)
set -euo pipefail
python3 /tmp/normalize-any.py /tmp/seed-platform-public.py || true
python3 /tmp/normalize-any.py /tmp/wipe-and-redeploy-v1-mixed.py || true
sudo -n python3 -u /tmp/seed-platform-public.py
echo "=== starting deploy ==="
sudo -n python3 -u /tmp/wipe-and-redeploy-v1-mixed.py deploy
