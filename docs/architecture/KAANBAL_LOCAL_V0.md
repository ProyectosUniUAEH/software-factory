# Kaanbal Local v0.1 — Arquitectura

## Alcance v0.1

Instalación reproducible en Ubuntu Server single-node:

- K3s, ArgoCD, Ingress
- Kaanbal API + Console
- GitOps (`infra-gitops`)
- Cloudflare Tunnel + Tailscale
- PostgreSQL
- FagoLab (app vertical)
- `kaanbal doctor`, backup inicial

## Vista simplificada

```text
Usuarios → Console / FagoLab / otras apps
              ↓
Kaanbal Control Plane (API, templates, GitOps, DNS, secretos)
              ↓
K3s + ArgoCD + Ingress + Cloudflare Tunnel + Tailscale
              ↓
Workloads: fago-api, fago-ui, apps generadas desde plantillas
```

## Modelo de repos (post-instalación)

El **monorepo de distribución** contiene el instalador. Al instalar, el sistema materializa repos separados en la org del cliente:

| Repo | Rol |
|------|-----|
| `kaanbal-api` | Backend FastAPI |
| `kaanbal-console` | UI Vue |
| `kaanbal-templates` | Catálogo de plantillas |
| `infra-gitops` | Manifiestos K8s + ArgoCD |
| `{app-name}` | Un repo por app desplegada (CI propio) |

Flujo app: `AppDeployer` crea repo → genera CI → build/push Docker Hub → patch overlay en `infra-gitops` → ArgoCD sync.

## Servidor lab

- IP: `192.168.1.198`
- SSH alias: `andres-lan`
- Perfil: `lab-standard`
- Iteración: LXD snapshots; aceptación: metal

## Instalador web

`SOFTWARE_FACTORY/installer/server.py` — Python stdlib, puerto 3000, wizard Acuaponsito.

Pasos: sistema → k3s → nodo → argocd → IA → regcred → tailscale → cloudflared → gitops → acceso.
