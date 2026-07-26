# Agent Worklog - Kaanbal Engine

Este archivo es el indice raiz para registrar lo que hacen los agentes en este workspace.

La regla simple: cada pedido importante debe quedar documentado como un Markdown dentro de `agent-worklog/`, con contexto, decisiones, comandos/evidencia y estado final. Este archivo solo resume y apunta a cada entrada.

## Convencion

- Carpeta de trabajo: `agent-worklog/`
- Formato de entrada: `YYYY-MM-DD-slug.md`
- Plantilla: `agent-worklog/TEMPLATE.md`
- No guardar secretos, tokens, passwords, llaves privadas ni contenido de `_private/`.
- Si se usan credenciales, documentar solo la ruta y el proposito, no el valor.
- Si se ejecutan comandos contra VPS/cluster, guardar evidencia resumida: comando, host, resultado esperado, resultado observado.

## Contexto operativo rapido

- Proyecto: Kaanbal Engine, PaaS Kubernetes-native.
- Workspace raiz: `C:\Users\andre\OneDrive\Documents\DEV\SOFTWARE FACTORY`
- Documentos base: `AGENTS.md`, `.agent/README.md`, `.agent/context/PROJECT.md`, `.agent/context/ARCHITECTURE.md`, `.agent/ROADMAP.md`, `.agent/LESSONS.md`.
- DEV VPS: `161.97.112.80`
- PROD VPS: `167.86.69.250`
- PEM DEV documentado: `_private/dev/keys/vps.pem`
- PEM PROD documentado: `_private/prod/keys/vps.pem`
- Regla de seguridad: nunca tocar PROD salvo pedido explicito.

## Entradas

| Fecha | Entrada | Estado | Resumen |
|---|---|---|---|
| 2026-05-24 | [DB bindings por ambiente y verificacion VPS](agent-worklog/2026-05-24-db-bindings-websocket-vps.md) | Implementado | Agregada seleccion de bases existentes por ambiente en backends; subido a GitHub/GitOps, pendiente confirmar sync directo en VPS. |
| 2026-05-24 | [Sistema de bitacora para agentes](agent-worklog/2026-05-24-agent-worklog-system.md) | Hecho | Se crea esta convencion para registrar cada pedido en Markdown. |

## Como debe usarlo el siguiente agente

1. Leer `AGENTS.md` y `.agent/README.md`.
2. Leer la entrada mas reciente en `agent-worklog/`.
3. Crear una nueva entrada desde `agent-worklog/TEMPLATE.md` antes o durante el trabajo.
4. Actualizar la entrada con evidencia real antes de cerrar.
5. Agregar una fila a la tabla de este indice.
