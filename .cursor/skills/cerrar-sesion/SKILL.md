---
name: cerrar-sesion
description: Cierra sesión Kaanbal con evidencia, actualiza STATE.md y crea archivo en AGENTS/sessions/. Usar cuando el usuario dice "cierra sesión".
---

# Cerrar sesión

## Pasos

1. `git status` en repos tocados — sin cambios sin push.
2. Si hubo PR: confirmar CI / estado.
3. Crear `AGENTS/sessions/YYYY-MM-DD-HHMM-tema.md` (template en `AGENTS/sessions/TEMPLATE.md`).
4. Actualizar `AGENTS/STATE.md` si cambió el sistema.
5. Actualizar `KAANBAL_IMPLEMENTATION_STATUS.md` si cerró un bloqueador o fase.
6. Limpiar scripts desechables en `AGENTS/labs/`.
7. Responder: "Sesión cerrada" + ruta del archivo.

## Bitácora académica (opcional)

Si el trabajo tiene valor investigación, anotar en repo `kaanbal-research` cuando exista.
