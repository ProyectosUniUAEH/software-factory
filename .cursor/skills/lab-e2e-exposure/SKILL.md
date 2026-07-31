---
name: lab-e2e-exposure
description: >-
  Smoke E2E de exposiciones Kaanbal en lab andres-lan: public HTTPS, Tailscale
  MagicDNS, cluster-internal, bindings DB. Usar tras cambios de deployer,
  exposure switch, o cuando el usuario pida probar matrix / VPN / DNS.
---

# Lab E2E Exposure

## Preflight

```bash
ssh andres-lan "sudo -n k3s kubectl get pods -n prod --no-headers | head -20"
ssh andres-lan "sudo -n k3s kubectl get ingress -A"
ssh andres-lan "sudo -n k3s kubectl -n tailscale get pods"
```

## Smokes (subir script, no one-liner PowerShell)

Crear `/tmp/e2e-exposure.sh` en el lab:

1. **Public:** `curl -sS -o /dev/null -w '%{http_code}' https://{host}.softwarefactory.site/`
2. **API:** `https://kaanbal-api.softwarefactory.site/health`
3. **Tailscale device list:** `sudo python3 tools/list-ts-devices.py` (solo hostnames)
4. **Cluster DNS binding:** desde un pod curl/nc a `{db}.{env}.svc.cluster.local:{port}`
5. **Argo:** apps Synced/Healthy

## Salida esperada al usuario

Tabla corta: app | env | modo | URL | HTTP | nota. Sin secretos.

## If fails VPN

1. ACL tags `tag:k8s` / grant `autogroup:member → tag:k8s`
2. Annotation `tailscale.com/expose=true` en Service
3. Pod `ts-*` Running en ns `tailscale`
4. Device online en API Tailscale
5. **Limpiar remanentes:** `sudo python3 tools/cleanup-tailscale-orphans.py --apply`
6. Re-registrar proxy: borrar STS/secret `ts-*` del app + restart operator (`tools/fix-and-clean-ts-lab.sh`)
