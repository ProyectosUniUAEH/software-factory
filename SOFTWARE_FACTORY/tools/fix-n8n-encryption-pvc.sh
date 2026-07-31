#!/usr/bin/env bash
# Fix n8n CrashLoop: PVC has old encryption key, secret was regenerated.
# Wipe data PVC and restart StatefulSet (lab OK — empty n8n data).
set -euo pipefail
APP="${1:-n8n-lab1}"
for ns in prod dev staging; do
  if sudo -n kubectl -n "$ns" get sts "$APP" >/dev/null 2>&1; then
    echo "[$ns] scale sts/$APP → 0"
    sudo -n kubectl -n "$ns" scale sts/"$APP" --replicas=0
    sudo -n kubectl -n "$ns" wait --for=delete pod -l app="$APP" --timeout=90s 2>/dev/null || true
    for pvc in $(sudo -n kubectl -n "$ns" get pvc -o name 2>/dev/null | grep "$APP" || true); do
      echo "[$ns] delete $pvc"
      sudo -n kubectl -n "$ns" delete "$pvc" --wait=true
    done
    echo "[$ns] scale sts/$APP → 1"
    sudo -n kubectl -n "$ns" scale sts/"$APP" --replicas=1
  else
    echo "[$ns] no sts/$APP"
  fi
done
echo "DONE"
for ns in prod dev; do
  sudo -n kubectl -n "$ns" get pods -l app="$APP" 2>/dev/null || true
done
