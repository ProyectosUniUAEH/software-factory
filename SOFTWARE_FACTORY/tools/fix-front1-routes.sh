#!/usr/bin/env bash
set -euo pipefail
K="sudo k3s kubectl"

# Staging: correct hostname (template overlay missed env prefix)
$K -n staging patch ingress front1 --type=merge -p '
spec:
  rules:
  - host: staging-front1.softwarefactory.site
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: front1
            port:
              number: 80
  tls:
  - hosts:
    - staging-front1.softwarefactory.site
    secretName: tls-staging-front1
'

# Dev: tailscale-only — no public ingress (already deleted if re-run)
$K -n dev delete ingress front1 --ignore-not-found

echo "staging host: $($K -n staging get ingress front1 -o jsonpath='{.spec.rules[0].host}')"
echo "dev ingress: $($K -n dev get ingress front1 2>&1 || echo none)"
