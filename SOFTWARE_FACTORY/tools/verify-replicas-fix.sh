#!/usr/bin/env bash
set -euo pipefail
POD=$(sudo -n kubectl -n prod get pod -l app=kaanbal-api -o jsonpath='{.items[0].metadata.name}')
echo "POD=$POD"
sudo -n kubectl -n prod exec "$POD" -- grep -n 'Only touch replicas for off' /app/app/services/exposure/switch_service.py | head -3
sudo -n kubectl -n prod exec "$POD" -- grep -n '_detect_workload_kinds' /app/app/services/exposure/switch_service.py | head -3
echo IMAGE=$(sudo -n kubectl -n prod get deploy kaanbal-api -o jsonpath='{.spec.template.spec.containers[0].image}')
