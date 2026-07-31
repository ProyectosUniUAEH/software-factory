# Bitácora — Exposure Lifecycle + Bindings + Instalador

> **Estado vivo.** Todo agente que retome este trabajo DEBE leer este archivo completo, actualizar la sección «Progreso» al cerrar cada subtarea, y no inventar fases nuevas sin registrarlas aquí.
>
> **Frase mágica (usuario → agente):** `continua bitácora exposición` o `/kaanbal-exposure`
>
> **Skill obligatorio:** `.cursor/skills/exposure-lifecycle/SKILL.md`

**Actualizado:** 2026-07-28  
**Owner lab:** `ssh andres-lan` (host Ubuntu, k3s, dominio `softwarefactory.site`)  
**Checkout servidor:** `~/kaanbal-next`  
**Credenciales:** `/etc/kaanbal/installer.env` (nunca volcar secretos al chat)  
**Workspace local:** `c:\Users\andre\Documents\GitHub\software-factory\SOFTWARE_FACTORY`

---

## 0. Contexto mínimo (mismo contacto que el agente anterior)

### Qué es Kaanbal aquí
Plataforma PaaS sobre k3s: consola Vue + API FastAPI + ArgoCD + Vault + Traefik + Cloudflare Tunnel + Tailscale operator. Apps de usuario se despliegan desde templates (`kaanbal-templates`) mutando overlays en `infra-gitops`.

### Lab actual (post wipe + reinstall 2026-07-28)
- Wipe Ubuntu + reinstall unattended OK.
- Core quedó mal en `tailnet` → consola sin Ingress; se forzó a **public** con `tools/switch-core-public.py`.
- Consola/API públicas OK: `https://kaanbal-console.softwarefactory.site`, `https://kaanbal-api.softwarefactory.site`.
- Bug `install.sh`: `--env /etc/kaanbal/installer.env` truncaba el mismo archivo (fix local aplicado; verificar en repo).
- App `test-vue`: prod+staging **public** (Ingress OK); **dev = Tailscale** hostname `dev-test-vue.tail31971f.ts.net` (proxy Running + device en API). ACL member→k8s aplicada; falta confirmación humana opcional.
- Código Fase 1: orquestador/scaffold listo; **wire AppDeployer pendiente** (sigue iteración en agente, no bloquea uso public).

### Pitfalls operativos (Windows → SSH)
- PowerShell rompe `$(...)`, pipes anidados, heredocs. Preferir: subir script → `tr -d '\r'` → `sudo python3 -u` / `bash`.
- No imprimir valores de `installer.env` en chat.
- No borrar Applications ArgoCD protegidas (`applicationsets`, `core-config`, `vault`, `tailscale-operator`, `kaanbal-*`).
- **Tailscale admin sucio:** tras wipe/redeploy quedan machines offline (`staging-lab-*`, `tailscale-operator` viejo). Siempre limpiar con `tools/cleanup-tailscale-orphans.py --apply` (o `--wipe-all-tagged` en wipe total). Integrado en `wipe-ubuntu-kaanbal.sh` paso 0.

### Archivos clave
| Área | Ruta |
|------|------|
| Deployer (hoy monolito) | `kaanbal-api/app/services/app_deployer.py` |
| Models exposure | `kaanbal-api/app/models.py` → `ExposureType` |
| Reglas categoría | `kaanbal-api/app/defaults.py` → `EXPOSURE_RULES` |
| Apps router | `kaanbal-api/app/routers/apps.py` |
| Catalog | `kaanbal-templates/catalog.json` |
| Installer | `installer/server.py`, `installer/unattended.py`, `install.sh` |
| Issues conocidos | `docs/INSTALLER_KNOWN_ISSUES.md` |
| Plan mixed lab | `docs/V1_MIXED_REDEPLOY_PLAN.md` |

---

## 1. Decisión de arquitectura: servicios independientes

Cada preocupación es un **servicio idempotente** con reintentos propios. El orquestador no hace DNS “inline” ni espera Tailscale en el mismo try que Argo.

```
ExposureOrchestrator (API)
 ├── ExposureGitOpsService     # reescribe overlays (Ingress/TS/LAN/off)
 ├── DnsPublisherService        # Cloudflare CNAME/A — retry/backoff
 ├── TailscalePublisherService  # annotations + wait device online — retry
 ├── LanPublisherService        # NodePort + cluster_lan_ip
 ├── BindingInjectorService     # Vault → secretGenerator {ALIAS}_*
 ├── GitOpsReconcilerService    # push infra-gitops + Argo hard-refresh + wait Healthy
 └── LifecycleService          # stop/start/scale (replicas + quitar expositores)
```

### Contrato de cada servicio
1. **Idempotente:** re-ejecutar = mismo estado deseado.
2. **Reintentos:** errores transitorios (DNS CF 5xx, Argo NotReady, TS device offline) con backoff exponencial + tope.
3. **Resultado tipado:** `{ ok, status, attempts, detail, urls? }` — el orquestador agrega sin abortar todo si un publisher no-crítico falla (ej. DNS tarda: marca `pending_dns`, app Healthy en cluster).
4. **Orden seguro anti-carrera:**
   1. Bindings (secrets)  
   2. GitOps overlays + push  
   3. Argo sync + wait workloads  
   4. En paralelo: DnsPublisher ∥ TailscalePublisher ∥ LanPublisher  
   5. Probe URLs según modo  
5. **Compensación:** al bajar de `public→internal/off`, DnsPublisher **borra** registro; TailscalePublisher limpia annotations/devices huérfanos.

### Modos de exposición (enum objetivo)
| Modo | Superficie |
|------|------------|
| `public` | Ingress Traefik + CF HTTPS + subdominio |
| `tailscale` | MagicDNS `{env}-{app}.ts.net` |
| `lan` | NodePort / IP LAN del nodo (NUEVO) |
| `internal` | Solo `{app}.{env}.svc.cluster.local` |
| `off` | Sin expositores + replicas=0 |
| `both` | Atajo: paths públicos + resto VPN (n8n webhooks) |

Por ambiente (`dev`/`staging`/`prod`) y opcionalmente por puerto (`port_exposure`).

### Bindings DB
Siempre cluster DNS + Vault. Vars: `{ALIAS}_HOST|_PORT|_USER|_PASSWORD|_DATABASE|_URI` (+ `DB_POSTGRESDB_*` para n8n). Independiente de exposición.

---

## 2. Fases

### Fase 0 — Contrato (enum/UI/schema) — DONE
- [x] Añadir `LAN`, `OFF` a `ExposureType`
- [x] Actualizar `EXPOSURE_RULES` (workflow incluye `both`; lan/off)
- [x] Catalog labels: internal=cluster, lan=red local, off
- [x] Schema create-app alineado
- [x] Wizard.vue modos alineados
- [x] `connection_info` en Orchestrator

### Fase 1 — Motor deploy + servicios + fix VPN — DONE
- [x] Paquete `kaanbal-api/app/services/exposure/` (types, retry, dns, ts, orchestrator)
- [x] Unit tests publishers (3 OK) + dockerhub/traefik contract (2 OK)
- [x] ACL Tailscale: grant `autogroup:member → tag:k8s*` aplicado en lab
- [x] Limpieza Tailscale orphans/duplicates + wipe paso 0
- [x] Wire deployer DNS/TS → DnsPublisherService / TailscalePublisherService (retries)
- [x] Traefik (+nginx) WS annotations en `_get_protocol_annotations`
- [x] `both` en path docker-hub (`_generate_webhook_ingress` + `_patch_env_domains_for_exposure`)
- [x] ExposureGitOpsService / Reconciler / Lan / Lifecycle (stubs listos; GitOps mutación vía façade)
- [x] Smoke usuario: app `dev` MagicDNS desde cliente Tailscale Windows (OK 2026-07-28 tras re-login)
- [ ] BindingInjectorService extracción completa (aún en deployer; Fase 4)

### Fase 2 — Switch post-deploy — IN PROGRESS (API + inventario)
- [x] `PATCH /apps/{name}/exposure` (`ExposureSwitchService`)
- [x] `POST .../environments/{env}/stop|start|scale`
- [x] Wire switch → GitOps mutate + push + DNS/TS publishers
- [x] Unit tests validación switch (5 OK; suite total 10)
- [x] `connection_inventory` desired/observed + `GET /exposure/status` (poll post-race)
- [x] Gates: wait proyección K8s + probe HTTP host **canónico** antes de `validated`
- [ ] Smoke E2E en lab: switch test-vue env (public↔tailscale) vía UI post-rebuild
- [x] UI matrix (Fase 5) consumiendo estos endpoints

**Hostname canónico (no confundir con MagicDNS):**
| Env | Public | Tailscale |
|-----|--------|-----------|
| prod | `{app}.{domain}` ej. `test-vue.softwarefactory.site` | `prod-{app}.{ts.net}` |
| staging/dev | `{env}-{app}.{domain}` | `{env}-{app}.{ts.net}` |

`prod-test-vue.softwarefactory.site` → 404 Traefik (host no existe). Abrir `https://test-vue.softwarefactory.site`.
Argo/CF/cert pueden tardar 30–120s: consola queda en **Validating…** y hace poll a `/exposure/status`.

### Fase 3 — Multi-URL (n8n / API+WS / EMQX) — DONE (code) + smoke pendiente
- [x] `connection_surfaces.py`: editor / webhook / mcp / api / ws / dashboard
- [x] Catalog n8n: `WEBHOOK_URL` + `N8N_EDITOR_BASE_URL`; private solo editor; surfaces + `/mcp/`
- [x] Deployer + switch enriquecen `connection_info.per_env_exposure`
- [x] Tests surfaces (4 OK) incl. EMQX L4 mqtt/ws vs L7 dashboard
- [x] Catalog EMQX: surfaces + layer L4/L7
- [x] Fix n8n deploy: TLS JSON6902 gated on `ingress_cluster_issuer` (CF edge; sin `/spec/tls`)
- [x] Lab: Vault sealed tras restart → unseal (`tools/unseal-vault-lab.py`); 503 era seal no código
- [ ] Smoke deploy n8n `both` en lab (humano)
- [ ] Smoke PATCH exposure en lab (Fase 2)
### Fase 4 — Bindings robustos
- [ ] Preflight Vault+DNS+TCP
- [ ] Re-inyectar en switch si cambia binding
- [ ] Unificar Links vs bindings

### Fase 5 — Consola UI matrix — IN PROGRESS
- [x] `ExposureManagerModal.vue` — env×modo + enable/remove + ops console
- [x] Wire desde Apps → Environments → “Manage exposure” (+ menú ⋮)
- [x] API wrappers `services/appsApi.js` (PATCH exposure, scale/stop/start, enable/remove env, status)
- [x] Backend `POST/DELETE .../environments/{env}` (ensure/remove)
- [x] Badges validated/pending/drift + Refresh status + poll Validating…
- [ ] Rebuild console (+ api) en lab y smoke en `test-vue`
- [x] Panel URLs canónicas Public host / VPN host
### Fase 6 — Instalador desatendido
- [ ] Defaults core `public` en cloud
- [ ] Preflight Traefik/CF/TS/Vault/Argo (+ grants ACL)
- [ ] Smoke post-install + fix truncate install.sh verificado
- [ ] Documentar I-* en INSTALLER_KNOWN_ISSUES

---

## 3. Progreso (log)

| Fecha | Agente | Qué | Resultado |
|-------|--------|-----|-----------|
| 2026-07-28 | Cursor Grok | Plan + servicios independientes + skills/rules/comando | Registrado |
| 2026-07-28 | Cursor Grok | Wipe+reinstall+console public | Hecho (sesión previa) |
| 2026-07-28 | Cursor Grok | Fase 0 contrato (enum lan/off, catalog, schema, Wizard, EXPOSURE_RULES) | DONE |
| 2026-07-28 | Cursor Grok | Fase 1 scaffold `services/exposure/` + tests + ACL grant member→k8s en lab | ACL updated; wire deployer pendiente |
| 2026-07-28 | Cursor Grok | Status smoke: core 200; test-vue prod/staging public; dev-test-vue MagicDNS + proxy Running | Usuario: 1 prueba VPN opcional |
| 2026-07-28 | Cursor Grok | Regla: limpia Tailscale; orphans+dupes; proxy re-reg | Hecho |
| 2026-07-28 | Cursor Grok | E2E: lab OK; Windows estaba logged out | Usuario reconectó Tailscale |
| 2026-07-28 | humano+agente | MagicDNS `dev-test-vue` visible y app OK | Fase 1 cerrada; arranca Fase 2 |
| 2026-07-28 | Cursor Grok | Fase 2 API: PATCH exposure + stop/start/scale + ExposureSwitchService + tests | API lista; falta smoke lab / UI |
| 2026-07-28 | Cursor Grok | Fase 3 surfaces + catalog n8n + ciclo `rebuild-platform.sh` (api/core/wipe-full) | Rebuild selectivo api+templates en curso |
| 2026-07-28 | Cursor Grok | Rebuild selectivo: `api` → `prod-c0b57bb` live; `templates` fa1bdd7; smoke OpenAPI `/exposure` | Fase 3 code en cluster; falta smoke n8n/switch humano |
| 2026-07-28 | Cursor Grok | Fase 5 UI: ExposureManagerModal + enable/remove env API + rebuild console `prod-056dec7` | Listo para smoke humano en Apps |
| 2026-07-28 | Cursor Grok | Inventario desired/observed + GET status + probe host canónico + UI Validating poll | Rebuild api+console pendiente |
| 2026-07-29 | Cursor Grok | n8n deploy fail: Vault sealed (503) + TLS JSON6902 sin issuer; unseal + gate TLS patches | API `prod-d22197d` live; Vault unsealed; **humano: reintentar n8n** |
| 2026-07-29 | Cursor Grok | Wizard n8n: quitar Mixed; Public\|VPN por env; catalog mode=public | Rebuild console+templates; smoke 2 envs |

---

## 3b. Smoke manual MVP (orden — productiva `andres-lan`)

Consola: `https://kaanbal.softwarefactory.site`  
Antes de cada deploy: Vault **unsealed** (`python3 tools/unseal-vault-lab.py` si 503).

| # | App | Cómo | Qué validar | ¿Listo ya? |
|---|-----|------|-------------|------------|
| 0 | test-vue (ya existe) | Manage exposure public↔VPN | Host canónico prod = `{app}.domain`; Validating… | Sí (regresión) |
| 1 | **n8n** | Wizard → n8n, envs `dev`+`prod`, exposure **Mixed/both** (o VPN+public paths) | Deploy OK; editor vía MagicDNS; webhook público `/webhook/` | **Tras rebuild API** (este fix) |
| 2 | EMQX | Wizard → EMQX, exposure **VPN** | Dashboard MagicDNS; MQTT L4 en inventory | Sí (catálogo listo; tras n8n) |
| 3 | Mongo / Postgres | Wizard config-only, **internal** o VPN | Nunca Ingress público; bind Vault | Sí |
| 4 | FastAPI | Scaffold + public/VPN | `/` API + `/ws` en surfaces | Sí |
| 5 | Vue / React | Scaffold public | UI HTTPS canónico | Sí (vue ya) |

**n8n hosts esperados (prod):**
- Público (webhooks): `https://n8nlab.softwarefactory.site/webhook/` (nombre real de la app)
- Editor VPN: `http://prod-n8nlab.tail….ts.net/`

Si Vault vuelve sealed tras reboot del nodo: `scp tools/unseal-vault-lab.py` → `python3 /tmp/unseal-vault-lab.py` en `andres-lan`.

## 5. Ciclo de release (selectivo vs wipe)

**Regla:** cada fase terminada vive en el código que el instalador empaqueta
(`kaanbal-api`, `kaanbal-templates`, `installer/`, `infra-gitops` render). Quien
descarga Software Factory + `install.sh --unattended` obtiene el mismo
comportamiento que el lab.

### Cuándo NO hacer wipe
| Cambio | Comando |
|--------|---------|
| API / deployer / exposure switch / surfaces | `sudo bash tools/rebuild-platform.sh api` |
| Consola UI | `sudo bash tools/rebuild-platform.sh console` |
| Catalog / templates | `sudo bash tools/rebuild-platform.sh templates` |
| Solo scripts instalador (próximo install) | `sudo bash tools/rebuild-platform.sh installer-sync` |
| api+console+agent+templates | `sudo bash tools/rebuild-platform.sh core` |

### Cuándo sí wipe total
Solo si el cluster está irrecuperable o hay que validar from-zero:

```bash
sudo bash tools/rebuild-platform.sh wipe-full
# = cleanup-tailscale --wipe-all-tagged + wipe-ubuntu-kaanbal.sh + install.sh --unattended
```

### Empaquetado por fase (checklist al cerrar fase)
- [x] Código en repo canónico (api/templates/installer) — Fase 2–3 en `kaanbal-api` + catalog
- [x] Tests unitarios verdes (9 OK surfaces/publishers/dockerhub)
- [x] Bitácora actualizada
- [x] `rebuild-platform.sh api` + `templates` en lab (2026-07-28)
- [x] `install.sh` documenta rebuild selectivo vs wipe-full
- [ ] Si toca defaults de install: `installer/unattended.py` + `kaanbal-reinstall.env` ejemplo (Fase 6)

**Contrato empaquetado (Software Factory download = lab):**
el instalador (`install.sh` / `corebuild`) construye imágenes core desde el árbol
local empaquetado (`kaanbal-api`, `kaanbal-console`, `kaanbal-agent`) y publica
`kaanbal-templates`. Por eso cada fase cerrada debe estar en ese árbol antes del
siguiente release/instalación — no solo “parcheado a mano” en el cluster lab.

---

## 4. Cómo retomar (otro agente / otro proveedor)

1. Leer esta bitácora completa.
2. Leer skill `.cursor/skills/exposure-lifecycle/SKILL.md`.
3. Leer `handoff/START_HERE.md` + actualizar `handoff/CURRENT_STATE.md` al terminar.
4. `ssh andres-lan` solo con scripts subidos (no one-liners PowerShell frágiles).
5. Marcar checkboxes aquí; añadir fila en «Progreso».
6. Preferir `rebuild-platform.sh api|templates|console` sobre wipe-full.
7. Credenciales: leer keys de `/etc/kaanbal/installer.env`, nunca values en chat.

### Recordatorio corto para el usuario
Pegar en el chat nuevo:

```
continua bitácora exposición
Lee SOFTWARE_FACTORY/docs/EXPOSURE_LIFECYCLE_BITACORA.md y .cursor/skills/exposure-lifecycle/SKILL.md
Ejecuta la siguiente fase pendiente. Actualiza la bitácora.
```

O slash command: `/kaanbal-exposure`
