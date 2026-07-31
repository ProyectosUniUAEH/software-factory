---
name: tarea-iniciar
description: Inicia trabajo en ticket Jira SF. Lee ticket vía MCP Atlassian, crea rama SF-XXX-slug, mueve a In Progress. Usar con "inicia SF-123" o al empezar implementación.
---

# Tarea iniciar

## Entrada

- Clave Jira: `SF-XXX`

## Pasos

1. Leer ticket (MCP Atlassian o pedir al usuario pegar descripción).
2. Verificar criterios de aceptación y archivos en alcance.
3. Cargar reglas según `docs/CONTEXT_MAP.yaml` → `by_area`.
4. Crear rama: `git checkout -b SF-XXX-slug-corto`.
5. Comentar en Jira: "Iniciado — rama SF-XXX-slug-corto, agente Cursor".
6. Confirmar plan al usuario antes de editar archivos.

## Commit format

`SF-XXX tipo: descripción`

Tipos: feat, fix, docs, chore, refactor, test
