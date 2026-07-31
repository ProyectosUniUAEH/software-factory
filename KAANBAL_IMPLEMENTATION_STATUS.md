# Kaanbal — Estado de implementación

Actualizado: 2026-07-26

## Objetivo inmediato

Kaanbal Local v0.1: instalación reproducible en Ubuntu Server local (`192.168.1.198` / `ssh andres-lan`), con Kaanbal Core, GitOps, Cloudflare Tunnel, Tailscale y FagoLab como app vertical de prueba.

## Fase actual

**Fase 0 — Bootstrap de contexto y gobierno** (en progreso)

## Hecho en esta sesión

- [x] `.cursor/mcp.json` con Atlassian Rovo MCP
- [x] `AGENTS.md` unificado
- [x] `docs/CONTEXT_MAP.yaml` (grafo de contexto)
- [x] Reglas Cursor iniciales
- [x] Skills: abrir/cerrar sesión, tarea-iniciar/cerrar, preflight-lab
- [x] Board Miro sembrado con doc y diagrama inicial
- [x] Esquema `.env` global documentado
- [x] `*.pem` en `.gitignore` de fago-sistema

## Bloqueadores antes de primera instalación limpia

| ID | Bloqueador | Prioridad |
|----|------------|-----------|
| B1 | Repo `kaanbal-templates` no existe en org | Alta |
| B2 | ApplicationSets apuntan a `futurefarms-softwarefactory` | Alta |
| B3 | Placeholders hardcodeados (`automation.com.mx`, Docker Hub users) | Alta |
| B4 | `infra-gitops/.../secret.yaml` con credenciales versionadas | Alta |
| B5 | ADR org GitHub pendiente de confirmación | Media |

## Backlog Fase 0 (Jira SF)

| Key | Título | Estado |
|-----|--------|--------|
| [SF-1](https://asistenteia97.atlassian.net/browse/SF-1) | Epic Fase 0 | Por hacer |
| [SF-2](https://asistenteia97.atlassian.net/browse/SF-2) | Bootstrap contexto multiagente | ~90% (cerrar PR) |
| [SF-3](https://asistenteia97.atlassian.net/browse/SF-3) | ADR organización GitHub | Por hacer |
| [SF-4](https://asistenteia97.atlassian.net/browse/SF-4) | Limpiar hardcodes + secretos | Por hacer |
| [SF-5](https://asistenteia97.atlassian.net/browse/SF-5) | Repo kaanbal-templates | Por hacer |
| [SF-6](https://asistenteia97.atlassian.net/browse/SF-6) | Credenciales ~/.kaanbal/env | Por hacer |
| [SF-7](https://asistenteia97.atlassian.net/browse/SF-7) | Preflight servidor lab | Por hacer |
| [SF-8](https://asistenteia97.atlassian.net/browse/SF-8) | Primera instalación (milestone) | Por hacer |

## Servidor lab

- Host: `192.168.1.198`
- SSH: `ssh andres-lan`
- Estado: Ubuntu Server limpio, sin apps — pendiente inventario
- Estrategia: LXD para iteración rápida + metal para aceptación

## Evidencia de pruebas

Registrar en chats de Cursor con formato PRUEBA (ver `AGENTS.md`).
