# Agent Bootstrap (Root)

## Objective
This folder is the root entrypoint for any new agent or new chat session.

## Read Order
1. `AGENTS.md` (raíz del repo) ← contrato corto para Cursor
2. `AGENTS/START_HERE.md` ← este archivo (continuidad operativa)
3. `docs/CONTEXT_MAP.yaml` ← grafo de contexto
4. `KAANBAL_IMPLEMENTATION_STATUS.md` ← estado de fases
5. `AGENTS/STATE.md` ← snapshot operativo
6. `AGENTS/sessions/` ← últimos 2 archivos
7. `SOFTWARE_FACTORY/handoff/FLOW_CONTRACT.md` ← contrato de entrega (legacy VPS; adaptar a lab local)

## Enlaces activos (2026-07-26)

- Jira: https://asistenteia97.atlassian.net/jira/software/projects/SF
- Miro: https://miro.com/app/board/uXjVH3hIUGE=/
- Lab SSH: `ssh andres-lan` (192.168.1.198)

## Canonical Project Location
- Carpeta: `AGENTS/sessions/`
- Convención de nombre: `YYYY-MM-DD-HHMM-tema-corto.md`
- Los archivos se ordenan cronológicamente por nombre automáticamente.
- **Un agente nuevo debe leer solo los últimos 2 archivos** — no el historial completo.
- **Al cerrar sesión**, el agente DEBE crear un nuevo archivo en `AGENTS/sessions/` siguiendo el template `AGENTS/sessions/TEMPLATE.md`.
- El archivo de sesión resume: qué se hizo, qué commits se crearon, qué falló, lecciones aprendidas, y qué queda pendiente.
- No necesitas leer sesiones antiguas (más de 2 atrás) — el contexto acumulado ya vive en `STATE.md` y `FLOW_CONTRACT.md`.

## Canonical Project Location
- `SOFTWARE_FACTORY/`
- `SOFTWARE_FACTORY_SECRETS/`

## Operational Contract (Mandatory)
1. Trabajar con ticket Jira **SF-XXX** (proyecto SF, site asistenteia97).
2. Org POC actual: `ProyectosUniUAEH` (ver ADR-001 en `docs/adr/`).
3. Delivery is complete only after this chain:
	1. Push to main
	2. CI success
	3. `infra-gitops` updated
	4. Argo Synced/Healthy
	5. Runtime validation (health + websocket + DB binding)
3. Never close work with only local edits.

## Access Model (VPS + VPN)
1. Primary cluster access in this workspace is via SSH PEM to VPS (non-interactive checks).
2. VPN/private exposure model is Tailscale for services configured as private.
3. Public exposure is via nginx ingress on `*.futurefarms.mx`.
4. If app is private-only, validate via Tailscale endpoint instead of public hostname.

## SSH Quick Start (Validated)
1. PEM path:
	1. `SOFTWARE_FACTORY_SECRETS/SOFTWARE_FACTORY_SECRETS/dev/keys/vps.pem`
2. Standard connection test:
	1. `ssh -i "SOFTWARE_FACTORY_SECRETS/SOFTWARE_FACTORY_SECRETS/dev/keys/vps.pem" -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15 root@194.163.191.139 "echo CONNECTED; whoami; hostname"`
3. Expected output includes:
	1. `CONNECTED`
	2. `root`
	3. remote host (example `vmi3317881`)

## Fast Continuation Protocol
1. Validate current Argo status for the app under work.
2. Validate health endpoint and websocket handshake.
3. Validate DB binding env vars and connectivity.
4. Continue only on top of latest remote main in each repo.

## Mandatory Validation Pack (Per App)
1. Argo:
	1. Application in dev/prod must be `Synced` and `Healthy`.
2. HTTP:
	1. `GET /health` must return `200`.
3. WebSocket:
	1. `/ws` must answer `101 Switching Protocols` when tested with valid WS headers.
4. Database binding:
	1. Pod has binding env vars (`*_HOST`, `*_PORT`, `*_URI`).
	2. Pod can reach DB service port.

## Known Platform Lessons (Do Not Regress)
1. Overlay `kustomization.yaml` must keep `resources` indentation with `  - ../../base`.
2. Generated ingress YAML must keep valid nested indentation in tls/rules/paths.
3. Do not generate `nginx.ingress.kubernetes.io/configuration-snippet` (blocked by cluster admission policy).
4. Do not force GRPC backend annotation on non-GRPC routes.
5. Generated app deployments must load generated secrets for DB bindings.

## If Deployment Fails
1. Check Argo condition message first.
2. If error says `invalid Kustomization yaml line 5`, inspect overlay `kustomization.yaml` resources indentation.
3. If ingress sync fails by webhook, remove blocked annotations and resync.
4. If public `/health` works but `/ws` is 404, validate app runtime route registration and websocket enable flags.

## Source Of Truth
- Operational contract and runbook: `SOFTWARE_FACTORY/handoff/FLOW_CONTRACT.md`
- Current execution status: `SOFTWARE_FACTORY/handoff/CURRENT_STATE.md`
- Session history: `AGENTS/sessions/` (últimas 2 entradas)

## Workspace Hygiene (Mandatory)
Reglas que el agente NUNCA debe romper:
1. **No crear archivos sueltos** en raíz del workspace ni en los repos fuera de las rutas establecidas.
2. **Scripts temporales, pruebas, diagnósticos** → crear SOLO en `AGENTS/labs/`. Esta carpeta es el sandbox del agente.
3. **Archivos de contexto o documentación** → solo en `AGENTS/` o `SOFTWARE_FACTORY/handoff/`.
4. **Nunca crear archivos** en raíz de `SOFTWARE_FACTORY/kaanbal-api/`, `kaanbal-console/`, `infra-gitops/` fuera de las convenciones de cada repo.
5. Al terminar la sesión, limpiar `AGENTS/labs/` de scripts desechables. Solo conservar los que tienen valor reutilizable.

## How To Start A Session (Protocolo de Inicio)
Cuando abras un nuevo chat con un agente:
1. Adjunta o menciona `AGENTS/START_HERE.md` — el agente lo leerá como primer paso.
2. El agente leerá en orden:
   - `AGENTS/START_HERE.md` → contexto operativo y reglas
   - `AGENTS/STATE.md` → estado actual del sistema
   - Los últimos 2 archivos en `AGENTS/sessions/` → qué ocurrió recientemente
   - `SOFTWARE_FACTORY/handoff/FLOW_CONTRACT.md` → contrato de entrega completo
3. El agente debe hacer `git pull` en los repos activos antes de tocar cualquier código.
4. El agente valida en VPS el estado de las apps antes de empezar cambios.
5. Tú describes el objetivo de la sesión y el agente confirma su plan antes de ejecutar.

## How To End A Session (Protocolo de Cierre)
Cuando termines el trabajo con el agente, pídele **"cierra la sesión"** y debe:
1. Hacer `git status` en todos los repos tocados — confirmar que no hay cambios sin push.
2. Validar en VPS que las apps modificadas están Synced/Healthy.
3. Crear `AGENTS/sessions/YYYY-MM-DD-HHMM-tema.md` con el template de `AGENTS/sessions/TEMPLATE.md`.
4. Actualizar `AGENTS/STATE.md` si cambió el estado del sistema (nuevas apps, commits críticos, lecciones).
5. Limpiar `AGENTS/labs/` eliminando scripts desechables de la sesión.
6. Confirmar al usuario: "Sesión cerrada. Archivo: `AGENTS/sessions/YYYY-MM-DD-HHMM-tema.md`".

## Closing Checklist (Al Terminar Sesión)
Antes de cerrar cualquier chat, el agente DEBE hacer esto:
1. Crear `AGENTS/sessions/YYYY-MM-DD-HHMM-tema.md` siguiendo el template.
2. Actualizar `AGENTS/STATE.md` si hubo cambios en el estado del sistema.
3. Confirmar que no hay commits locales sin push en repos activos (`git status`).
4. Confirmar que cualquier app modificada está Synced/Healthy en Argo.
5. Limpiar scripts desechables de `AGENTS/labs/`.
