# AGENTS/labs — Sandbox del Agente

Esta carpeta es el único lugar donde el agente puede crear scripts, pruebas, diagnósticos y archivos temporales.

## Reglas
- Todo script o archivo temporal creado durante una sesión va aquí.
- Al cerrar sesión: eliminar los scripts desechables. Conservar solo los reutilizables.
- No crear archivos fuera de esta carpeta salvo en las rutas establecidas de cada repo.

## Ejemplos de lo que va aquí
- Scripts de diagnóstico SSH / kubectl one-off
- Pruebas de conectividad o curl
- Scripts de validación ad-hoc
- Borradores antes de mover a un repo

## Ejemplos de lo que NO va aquí
- Manifiestos K8s definitivos → van en `infra-gitops/`
- Código de la plataforma → va en `kaanbal-api/` o `kaanbal-console/`
- Contexto de sesión → va en `AGENTS/sessions/`
