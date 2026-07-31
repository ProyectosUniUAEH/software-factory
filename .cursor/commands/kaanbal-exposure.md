# Continuar bitácora exposición Kaanbal

Lee y ejecuta:

1. `SOFTWARE_FACTORY/docs/EXPOSURE_LIFECYCLE_BITACORA.md` (progreso + siguiente fase)
2. `.cursor/skills/exposure-lifecycle/SKILL.md`
3. Si hay pruebas de lab: `.cursor/skills/lab-e2e-exposure/SKILL.md`

Instrucciones:
- Continúa **solo la siguiente fase pendiente** de la bitácora.
- Respeta servicios independientes con retries (DNS, Tailscale, GitOps, Bindings).
- No imprimas secretos de `/etc/kaanbal/installer.env`.
- Al terminar: marca checkboxes, añade fila en Progreso, actualiza `SOFTWARE_FACTORY/handoff/CURRENT_STATE.md`.
- SSH al lab vía scripts subidos (`tr -d '\r'`), no one-liners frágiles en PowerShell.
