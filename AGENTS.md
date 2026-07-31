# Kaanbal — Instrucciones para agentes

## Lee antes de trabajar

1. `docs/CONTEXT_MAP.yaml` — grafo de contexto (qué leer y cuándo)
2. `docs/vision/KAANBAL_VISION.md` — visión resumida
3. `KAANBAL_IMPLEMENTATION_STATUS.md` — estado actual
4. `AGENTS/STATE.md` — snapshot operativo
5. Ticket Jira asignado (proyecto **SF**, site `asistenteia97.atlassian.net`)

Handoff extenso (solo si hace falta): `../KAANBAL_MASTER_HANDOFF_CURSOR.md`

## Enlaces de trabajo

| Recurso | URL |
|---------|-----|
| Jira SF | https://asistenteia97.atlassian.net/jira/software/projects/SF |
| Miro Kaanbal | https://miro.com/app/board/uXjVH3hIUGE=/ |
| Repo producto | `ProyectosUniUAEH/software-factory` |
| Repo FagoLab | `ProyectosUniUAEH/fago-sistema` |
| Repo investigación | `ProyectosUniUAEH/kaanbal-research` (privado) |

## Reglas obligatorias

- Un ticket Jira → una rama → un PR → evidencia en el chat y en Jira.
- Nunca modificar `main` directamente.
- Nunca exponer secretos ni leer `.env` / `*.pem`.
- GitOps es la fuente de despliegue.
- Servidor lab: `ssh andres-lan` (solo lectura salvo aprobación explícita).
- Separar carril **producto** (este repo) de carril **académico** (`kaanbal-research`).

## Skills del flujo

| Comando | Skill |
|---------|-------|
| Inicio de sesión | `.cursor/skills/abrir-sesion/` |
| Cierre de sesión | `.cursor/skills/cerrar-sesion/` |
| Iniciar ticket | `.cursor/skills/tarea-iniciar/` |
| Cerrar ticket | `.cursor/skills/tarea-cerrar/` |
| Preflight lab | `.cursor/skills/preflight-lab/` |
| Documentar en Confluence | `.cursor/skills/documentador-confluence/` |

## Pruebas manuales

Documentar en **este chat** con formato:

```text
PRUEBA: SF-XXX — título
FECHA:
PRECONDICIONES:
PASOS:
RESULTADO ESPERADO:
RESULTADO OBTENIDO:
EVIDENCIA: (comando, screenshot, URL)
APROBADO: sí/no
```

## Subagentes recomendados

| Subagente | Cuándo |
|-----------|--------|
| `explore` | Mapear código desconocido |
| `shell` | Comandos en lab o git |
| `bugbot` | Revisión de PR antes de merge |
| `ci-investigator` | CI fallido |
