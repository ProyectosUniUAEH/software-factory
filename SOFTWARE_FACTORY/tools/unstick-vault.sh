#!/usr/bin/env bash
# Destraba una Application cuya operación quedó esperando por un recurso que
# nunca podrá volverse sano (un Ingress sin controlador, típicamente). Solo hace
# falta tras cambiar el baseline: una instalación nueva no llega a este estado.
set -uo pipefail
APP="${1:-vault}"
K="sudo -n k3s kubectl -n argocd"

echo "Cancelando la operación en curso de ${APP}..."
$K patch app "$APP" --type=json -p='[{"op":"remove","path":"/operation"}]' 2>&1 \
  || echo "  (no había operación en curso)"

echo "Forzando recarga del manifiesto desde Git..."
$K annotate app "$APP" argocd.argoproj.io/refresh=hard --overwrite 2>&1

sleep 20
echo "Borrando los recursos que ya no están en Git..."
sudo -n k3s kubectl -n vault delete ingress vault-ui --ignore-not-found 2>&1

sleep 40
echo
$K get app "$APP" 2>&1
sudo -n k3s kubectl -n vault get ingress 2>&1
