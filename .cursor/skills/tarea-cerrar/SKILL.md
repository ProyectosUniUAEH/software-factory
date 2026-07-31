---
name: tarea-cerrar
description: Cierra ticket Jira SF con PR, evidencia en Jira y bloque PRUEBA en chat. Usar al terminar implementación de SF-XXX.
---

# Tarea cerrar

## Entrada

- Clave Jira: `SF-XXX`
- Rama con commits listos

## Pasos

1. Ejecutar pruebas del ticket (automáticas + manuales).
2. Abrir PR: título `SF-XXX: resumen` → base `main`.
3. Comentar en Jira con:
   - Rama y commits
   - PR URL
   - Tests ejecutados
   - Riesgos / rollback
4. Mover ticket a **Ready for QA** (o Done si acordado).
5. Pegar en **este chat** bloque PRUEBA (ver AGENTS.md).

## Plantilla comentario Jira

```text
Implementación lista para revisión.

Rama: SF-XXX-slug
PR: <url>
Tests: <lista>
Rollback: <cómo revertir>
Evidencia chat: registrada en sesión Cursor
```

## Plantilla PRUEBA (chat)

```text
PRUEBA: SF-XXX — título
FECHA: YYYY-MM-DD
PRECONDICIONES:
PASOS:
RESULTADO ESPERADO:
RESULTADO OBTENIDO:
EVIDENCIA:
APROBADO: sí/no
```
