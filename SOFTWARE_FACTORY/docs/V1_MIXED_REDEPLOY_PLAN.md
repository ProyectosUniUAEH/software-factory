# Plan redeploy v1 — exposición mixta (3 ambientes)

## Orden lógico

```
1. WIPE apps de usuario (GitHub + Docker + ArgoCD + Vault + Tailscale orphans)
   Core Kaanbal se conserva (consola, api, vault, tunnel, operator).

2. lab-mongo + lab-pg          ← primero (fuente compartida)
3. lab-emqx                    ← multi-port complejo
4. lab-n8n  (+ binding lab-pg) ← workflow + BD
5. lab-api  (+ binding pg+mongo)
6. lab-react
```

## Matriz de exposición (uno de cada modo donde la categoría lo permite)

| App | prod | staging | dev |
|-----|------|---------|-----|
| lab-mongo / lab-pg | **tailscale** (VPN) | **tailscale** | **internal** (solo cluster) |
| lab-emqx | **public** | **tailscale** | **internal** |
| lab-n8n | **public** | **tailscale** | **tailscale** *(workflow no admite internal)* |
| lab-api | **public** | **tailscale** | **internal** |
| lab-react | **public** | **tailscale** | **tailscale** *(frontend no admite internal)* |

## Por qué este orden

1. **BD primero** — Vault genera credenciales; el resto las consume.
2. **EMQX/n8n después** — más piezas (puertos, webhooks, imagen oficial).
3. **API con bindings** — prueba la unión segura cluster-DNS (no internet).
4. **Frontend al final** — solo UI; no necesita BD directa en v1.

## Seguridad esperada

- `https://lab-pg|lab-mongo.softwarefactory.site` → **404**
- App→BD: `*.svc.cluster.local` + secretos Vault
- Admin BD: MagicDNS Tailscale

## Lecciones del wipe+redeploy (2026-07-28)

1. **Nunca borrar** ArgoCD `applicationsets` / `core-config` en un wipe de apps de usuario → `PROTECTED_ARGOCD_APPS`.
2. Tras recrear `datastore`, re-sembrar plataforma con `git_username` real (GitHub login) — `_resolve_github_login` / `seed-platform-public.py`.
3. Refrescar catálogo templates tras seed (automático en `seed_platform`).
4. **n8n**: bindings emiten `DB_POSTGRESDB_*`; memoria 2Gi; Service `{app}-http` ClusterIP + Ingress (I-09/I-10).
5. Templates config-only HTTP generan Ingress sin exigir `health_endpoint`.
6. Overlay Ingress patches: regex tolerante a blank lines (I-11) — React/Vue staging OK.

Ver `docs/INSTALLER_KNOWN_ISSUES.md` I-07…I-12.
