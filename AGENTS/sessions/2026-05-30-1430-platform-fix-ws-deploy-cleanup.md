# Session: 2026-05-30 — FastAPI WS deploy fix + platform hardening + workspace cleanup

## Objetivo de la sesión
Diagnosticar y corregir el fallo de despliegue de FastAPI con WebSockets ligado a base de datos, y asegurar que la plataforma no vuelva a generar manifiestos inválidos para ninguna app futura.

## Resumen ejecutivo
Se corrigió el generador de manifiestos K8s en `kaanbal-api` a nivel de plataforma, eliminando 4 bugs que afectaban a todas las apps generadas. Se validaron fast-api y fago-api en dev/prod (Synced/Healthy, health 200, WS 101). Se limpió el workspace local dejando solo los 4 repos esenciales + contexto de handoff. Se creó la estructura `AGENTS/` como entrypoint para futuros agentes.

## Trabajo realizado
- Diagnóstico SSH al VPS y revisión de ArgoCD para identificar causa raíz del fallo
- Fix del generador de manifiestos `app/services/app_deployer.py` en kaanbal-api (4 bugs)
- Reparación manual de fast-api overlays (dev + prod) en infra-gitops
- Reparación manual de fago-api overlays (dev + prod) en infra-gitops
- Validación de health + WS para fast-api y fago-api en ambos envs
- Creación de estructura `AGENTS/` con `START_HERE.md`, `STATE.md`, `sessions/`
- Limpieza del workspace: eliminación de `.agent/`, `.deploy-tmp/`, `agent-worklog/`, `infra-gitops-fix/`
- Consolidación de contexto histórico en `SOFTWARE_FACTORY/handoff/`
- Commit del cleanup al repo raíz SOFTWARE_FACTORY

## Commits creados
| Repo | Commit | Descripción |
|---|---|---|
| `kaanbal-api` | `a7e608a` | fix(platform): harden ingress/kustomization generation for future APIs |
| `infra-gitops` | `33519d5` | fix(fast-api): kustomization + ingress structure dev+prod |
| `infra-gitops` | `2f5dcb8` | fix(fast-api): remove blocked annotation, add envFrom |
| `infra-gitops` | `24a6163` | fix(fago-api): same manifest bugs as fast-api repaired |
| `SOFTWARE_FACTORY` (root) | `bbc400e` | chore(workspace): cleanup legacy agent dirs, consolidate context |

## Apps desplegadas / validadas
| App | Env | Estado | Evidencia |
|---|---|---|---|
| `fast-api` | dev | Synced/Healthy | health 200, ws 101 |
| `fast-api` | prod | Synced/Healthy | health 200, ws 101 |
| `fago-api` | dev | Synced/Healthy | health 200 |
| `fago-api` | prod | Synced/Healthy | health 200 |
| `kaanbal-api` | prod | Synced/Healthy | imagen `prod-a7e608a` |

## Problemas encontrados y soluciones

- **Problema**: `invalid Kustomization: yaml: line 5: did not find expected key`
  - **Causa raíz**: El generador producía `- ../../base` sin indentación bajo `resources:`, rompiendo el YAML.
  - **Solución**: Cambiar a `  - ../../base` (2 espacios) en `_create_basic_overlay()` y `_add_kustomize_resource()`.

- **Problema**: Ingress YAML malformado bloqueaba kustomize build.
  - **Causa raíz**: `_write_public_ingress_for_port()` generaba bloques `tls/rules/paths` con indentación incorrecta.
  - **Solución**: Reescritura completa del template string con indentación 2/4 espacios correcta.

- **Problema**: Admission webhook rechazaba ingress generado.
  - **Error**: `nginx.ingress.kubernetes.io/configuration-snippet annotation cannot be used. Snippet directives are disabled`
  - **Causa raíz**: El generador incluía `configuration-snippet` para WebSocket, bloqueado por política del cluster.
  - **Solución**: Eliminar `configuration-snippet` de `_PROTOCOL_NGINX_ANNOTATIONS["websocket"]`. WS funciona solo con `proxy-http-version: 1.1` + timeouts.

- **Problema**: Secrets generados en overlay no llegaban al container.
  - **Causa raíz**: `secretGenerator` crea el Secret pero el Deployment no lo montaba.
  - **Solución**: Agregar `envFrom.secretRef` con `optional: true` a todos los Deployments generados.

## Lecciones aprendidas (no regresar)
- `resources:` en kustomization DEBE tener `  - ../../base` con 2 espacios — sin ellos falla silenciosamente en YAML parse.
- NUNCA generar `nginx.ingress.kubernetes.io/configuration-snippet` — el cluster lo bloquea via admission webhook.
- NUNCA forzar `backend-protocol: GRPC` en rutas que no son GRPC — revisar el nombre del puerto.
- Todo Deployment generado DEBE tener `envFrom.secretRef` con `optional: true` para cargar el Secret del overlay.
- WebSocket por curl requiere `--http1.1` + header `Sec-WebSocket-Key` válido de 16 bytes en base64. Sin eso el `101` no aparece.
- Los repos `kaanbal-api`, `kaanbal-console`, `infra-gitops` tienen su propio `.git` dentro de `SOFTWARE_FACTORY/`. Cada uno hace push a su remoto independiente en la org. El repo raíz `SOFTWARE_FACTORY` es el installer/packager, no la plataforma.

## Estado al cerrar la sesión
- Todos los repos con cambios tienen push hecho: **Sí**
- Apps activas en prod/dev Synced/Healthy: **Sí** (fast-api dev/prod, fago-api dev/prod, kaanbal-api prod)
- Commits locales sin push: ninguno en kaanbal-api, kaanbal-console, infra-gitops. Root SOFTWARE_FACTORY tiene `bbc400e` pendiente de push al remote `futurefarms-mx/softwarefactory`.

## Pendientes para la próxima sesión
- Hacer push del commit `bbc400e` al remote de SOFTWARE_FACTORY (`futurefarms-mx/softwarefactory`) si se trabaja desde otra máquina.
- El infra-gitops local está `ahead 0` del remote pero el remote puede haber recibido commits de ArgoCD pipeline — siempre hacer `git pull` antes de editar.
- Validar DB binding end-to-end (env vars en pod + conectividad al servicio de BD) para fast-api y fago-api.

## Repos tocados en esta sesión
- `futurefarms-softwarefactory/kaanbal-api` — rama main (commit `a7e608a`)
- `futurefarms-softwarefactory/infra-gitops` — rama main (commits `33519d5`, `2f5dcb8`, `24a6163`)
- `futurefarms-mx/softwarefactory` (root local) — rama main (commit `bbc400e`, push pendiente)
