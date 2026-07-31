#!/usr/bin/env bash
set -euo pipefail
SRC=/home/andres/kaanbal-reinstall.env
[[ -f "$SRC" ]] || { echo "missing $SRC"; exit 1; }
sudo -n mkdir -p /etc/kaanbal
sudo -n bash -c "tr -d '\r' < '$SRC' > /etc/kaanbal/installer.env && chmod 600 /etc/kaanbal/installer.env"
echo "keys:"
sudo -n bash -c "cut -d= -f1 /etc/kaanbal/installer.env | sort"
echo "bytes:$(sudo -n wc -c < /etc/kaanbal/installer.env)"
cd /home/andres/kaanbal-next
# quick config check only
sudo -n python3 -u installer/unattended.py --env /etc/kaanbal/installer.env --check-only --expect-reset 2>&1 | tee /home/andres/kaanbal-next/logs/preflight-check.log | tail -80
