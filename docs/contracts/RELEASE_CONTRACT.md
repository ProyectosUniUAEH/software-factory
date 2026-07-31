# Contrato de release

Un cambio **no está entregado** con solo código local.

## Cadena obligatoria

1. Ticket Jira (SF-XXX) con criterios de aceptación
2. Rama `SF-XXX-slug`
3. Implementación + pruebas automáticas
4. PR con evidencia
5. Revisión (humana o subagente bugbot)
6. Merge a `main`
7. CI exitoso
8. `infra-gitops` actualizado (si aplica)
9. ArgoCD Synced + Healthy
10. Health checks runtime
11. Comentario en Jira + registro PRUEBA en chat

## Validación por app

- `GET /health` → 200
- WebSocket → 101 (si aplica)
- Pods Ready
- DB binding presente
- Sin secretos en logs

## Rollback

Todo PR debe documentar cómo revertir (revert commit, tag anterior en overlay, Argo sync).
