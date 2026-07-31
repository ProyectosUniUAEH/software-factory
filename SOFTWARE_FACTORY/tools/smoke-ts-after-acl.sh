#!/usr/bin/env bash
# Smoke: list TS devices + curl MagicDNS from inside a TS proxy pod if possible
set -euo pipefail
echo "=== TS PODS ==="
sudo -n k3s kubectl -n tailscale get pods -o wide
echo "=== CONSOLE PROXY STATUS ==="
sudo -n k3s kubectl -n tailscale exec deploy/operator -- wget -qO- http://127.0.0.1:8080/ 2>/dev/null | head -c 100 || true
echo
echo "=== DEVICES (hostnames only) ==="
sudo -n python3 /home/andres/kaanbal-next/tools/list-ts-devices.py 2>/dev/null | grep -iE 'kaanbal|lab-|---' | head -40 || true
echo "=== CURL FROM TS CONSOLE PROXY TO ITSELF ==="
# Use the console proxy's peerapi / local status
sudo -n k3s kubectl -n tailscale exec ts-kaanbal-console-bnngn-0 -c tailscale -- \
  tailscale status 2>/dev/null | head -20 || echo "no console proxy"
echo "=== DONE ==="
