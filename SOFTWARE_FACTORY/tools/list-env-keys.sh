#!/usr/bin/env bash
# List env KEY names only (no values)
set -euo pipefail
echo "=== /etc/kaanbal/installer.env keys ==="
sudo -n grep -oE '^[A-Za-z0-9_-]+' /etc/kaanbal/installer.env 2>/dev/null | sort || echo MISSING
echo "=== /home/andres/kaanbal-reinstall.env keys ==="
grep -oE '^[A-Za-z0-9_-]+' /home/andres/kaanbal-reinstall.env 2>/dev/null | sort || echo MISSING
