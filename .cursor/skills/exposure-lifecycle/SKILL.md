---
name: exposure-lifecycle
description: >-
  Continúa el plan de exposición de apps Kaanbal (public/tailscale/lan/internal/off),
  bindings DB, switch post-deploy e instalador. Usar cuando el usuario diga
  "continua bitácora exposición", "/kaanbal-exposure", pida matrix de exposición,
  VPN MagicDNS, ciclo de vida de apps, o bindings a Postgres/Mongo.
---

# Exposure Lifecycle (Kaanbal)

## Obligatorio al inicio

1. Leer y respetar `SOFTWARE_FACTORY/docs/EXPOSURE_LIFECYCLE_BITACORA.md` (fuente de progreso).
2. Leer `SOFTWARE_FACTORY/handoff/START_HERE.md` si es chat nuevo.
3. No volcar secretos de `/etc/kaanbal/installer.env` al chat.
4. En Windows→SSH: subir scripts, `tr -d '\r'`, evitar `$()` / heredocs en PowerShell.

## Arquitectura a implementar

Servicios independientes bajo `kaanbal-api/app/services/exposure/`:

| Servicio | Responsabilidad | Retry |
|----------|-----------------|-------|
| `ExposureGitOpsService` | Mutar overlays Ingress/TS/LAN/off | validación kustomize |
| `DnsPublisherService` | Cloudflare DNS create/delete | backoff CF API |
| `TailscalePublisherService` | annotations + wait device | poll MagicDNS |
| `LanPublisherService` | NodePort + LAN IP | — |
| `BindingInjectorService` | Vault → `{ALIAS}_*` | wait secret ready |
| `GitOpsReconcilerService` | push + Argo hard refresh + Healthy | poll sync |
| `LifecycleService` | stop/start/scale | — |
| `ExposureOrchestrator` | orden anti-carrera + agrega resultados | — |

Orden: bindings → gitops push → argo wait → (dns ∥ ts ∥ lan) → probe.

## Fases

Ejecutar **solo la siguiente fase pendiente** de la bitácora. Al terminar:
- Marcar checkboxes.
- Añadir fila en «Progreso».
- Actualizar `handoff/CURRENT_STATE.md` (2-5 bullets).

## Lab

- Host: `ssh andres-lan`
- Código servidor: `~/kaanbal-next` (sincronizar desde `SOFTWARE_FACTORY` lo que cambies)
- Dominio: `softwarefactory.site`
- Core público: `kaanbal-console` / `kaanbal-api` vía Cloudflare

## Publicar cambios (NO wipe por defecto)

```bash
# Solo API (exposure switch, surfaces, deployer)
sudo bash tools/rebuild-platform.sh api
# Catalog/templates
sudo bash tools/rebuild-platform.sh templates
# From-zero solo si hace falta
sudo bash tools/rebuild-platform.sh wipe-full
```

Ver bitácora §5 Ciclo de release.

## Pruebas

Usar skill `lab-e2e-exposure` para smokes. Registrar evidencia en chat con códigos HTTP (sin tokens).

## Prohibido

- Borrar Applications ArgoCD core.
- `install.sh --env` apuntando al mismo path que escribe sin el fix de truncate.
- Exponer databases como `public`.
- Dejar sucio el admin de Tailscale tras wipe/redeploy: **siempre** correr
  `tools/cleanup-tailscale-orphans.py --apply` (o `--wipe-all-tagged` en wipe total).
  Remanentes offline (`staging-lab-*`, operators viejos) rompen la percepción de VPN
  y confunden MagicDNS.
