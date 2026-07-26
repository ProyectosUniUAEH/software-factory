# Kaanbal Web Installer 🌱

La primera impresión de la plataforma: un instalador web guiado por **Acuaponsito**
que convierte cualquier Linux (laptop WSL2, VPS Contabo, instancia cloud) en una
célula Kaanbal — con la misma UX en todos lados, estilo Contabo: IP + puerto + token.

## Uso

```bash
python3 installer/server.py
# imprime:  http://localhost:3000/?token=<token-de-sesión>
# en VPS:   http://<IP>:3000/?token=<token>
```

**Cero dependencias** — solo Python 3 stdlib. Nada de pip en la máquina del usuario.

## Flujo

1. **Bienvenida** — chequeo del sistema en vivo (RAM, CPU, disco, systemd, WSL,
   k3s/ArgoCD ya presentes). Acuaponsito saluda (clip de video).
2. **Conectividad** — recomienda fuerte *dominio propio + Cloudflare Tunnel*
   (la digitalización necesita nube desde el día uno), pero permite modo
   local/VPN sin fricción. Validaciones reales contra las APIs de Cloudflare,
   GitHub y Tailscale antes de tocar nada.
3. **Despliegue en vivo** — stepper + bitácora (terminal translúcida) por SSE.
   Los pasos son **idempotentes**: detectan lo ya instalado y lo marcan hecho,
   así el instalador también sirve como panel de verificación/reparación.
4. **Modo operativo** — credenciales de ArgoCD, port-forward automático,
   siguientes pasos. Handoff sin fricción.

## Acuaponsito

Los clips viven en `static/media/` (`clip_welcome.mp4`, `clip_listening.mp4`,
`clip_processing.mp4`, ~2.5MB c/u). Si se eliminan, la UI cae automáticamente
a un **Acuaponsito SVG animado** (flotando, parpadeo, hoja al viento) — el
flujo nunca depende de los videos. Estados: welcome / listening / processing /
success / error.

## Lecciones ya integradas (errores del primer intento en WSL2)

- `kubectl apply --server-side` para ArgoCD: el CRD de ApplicationSets excede
  el límite de 262KB de la anotación `last-applied-configuration`.
- `systemctl is-system-running` acepta `degraded` (WSL2 reporta eso a veces).
- Espera de rollout con timeout largo (primera descarga de imágenes es lenta).
- Token de sesión obligatorio en toda la API (como el instalador de Contabo).

## Arquitectura

```
installer/
├── server.py          # http.server stdlib: estático + API + SSE + pasos reales
└── static/
    ├── index.html     # 4 pantallas (bienvenida/modo/despliegue/operativo)
    ├── style.css      # estética eco-tech: auroras, estrellas, glass, glows
    ├── app.js         # state machine + EventSource + estados de Acuaponsito
    └── media/         # clips (opcionales, fallback SVG integrado)
```
