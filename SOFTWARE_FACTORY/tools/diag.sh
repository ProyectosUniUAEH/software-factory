#!/usr/bin/env bash
# Diagnóstico de una célula ya instalada. Solo lectura.
set -uo pipefail
K="sudo -n k3s kubectl"

echo "=== BITÁCORA DEL TÚNEL ==="
sudo -n python3 /home/andres/watch-install.py --once --tail 400 2>/dev/null \
  | grep -iE 'tunel|tunel|cloudflare|ingress|traefik|dns' || echo "(sin coincidencias)"

echo
echo "=== DEPLOYMENT CLOUDFLARED ==="
$K -n prod get deployment cloudflared -o wide 2>&1 || echo "(no existe)"

echo
echo "=== MANIFIESTO QUE SE APLICÓ ==="
ls -la /tmp/kaanbal-cloudflared.yaml 2>&1 || echo "(el reset borró /tmp/kaanbal-*)"

echo
echo "=== EVENTOS RECIENTES EN PROD ==="
$K -n prod get events --sort-by=.lastTimestamp 2>&1 | tail -25

echo
echo "=== INGRESSES ==="
$K -n prod get ingress -o wide 2>&1

echo
echo "=== SERVICIOS PROD ==="
$K -n prod get svc 2>&1

echo
echo "=== TRAEFIK ==="
$K -n kube-system get svc traefik 2>&1
