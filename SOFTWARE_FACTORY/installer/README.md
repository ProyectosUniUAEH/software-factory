# Kaanbal Web Installer 🌱

La primera impresión de la plataforma: un instalador web guiado por **Acuaponsito**
que convierte cualquier Linux (laptop WSL2, VPS Contabo, instancia cloud) en una
célula Kaanbal — con la misma UX en todos lados, estilo Contabo: IP + puerto + token.

## Uso recomendado (Ubuntu Server)

```bash
git clone https://github.com/ProyectosUniUAEH/software-factory.git
cd software-factory/SOFTWARE_FACTORY
sudo bash ./install.sh
# opcional: preimportar credenciales
sudo bash ./install.sh --env /ruta/segura/.env
```

El bootstrap pide privilegios una sola vez, crea un servicio systemd temporal y
muestra `http://<IP>:3000/?token=<token-temporal>`. El wizard instala k3s,
ArgoCD, los repos core y la conectividad. Cuando el administrador confirma su
usuario y contraseña, el token se revoca y el servicio privilegiado se apaga.

**Cero dependencias Python** — el backend usa solo stdlib.

## Reset de laboratorio

```bash
# Reinstalar desde cero conservando credenciales y recursos externos
sudo bash ./install.sh --reset-local --preserve-credentials

# Reinstalar y borrar también las credenciales locales
sudo bash ./install.sh --reset-local --wipe-credentials
```

El reset local nunca elimina repos GitHub, túneles/DNS Cloudflare, tokens Docker
Hub ni clientes Tailscale. Esos recursos requieren una operación externa
separada y con allowlist explícita.

Credenciales persistentes: `/etc/kaanbal/installer.env` (`root:root`, modo 600).
Estado recuperable: `/var/lib/kaanbal-installer/state.json`.

## Flujo

1. **Bienvenida** — chequeo del sistema en vivo (RAM, CPU, disco, systemd,
   privilegios temporales, k3s/ArgoCD).
2. **Conectividad** — recomienda fuerte *dominio propio + Cloudflare Tunnel*
   (la digitalización necesita nube desde el día uno), pero permite modo
   local/VPN sin fricción. Validaciones reales contra las APIs de Cloudflare,
   GitHub y Tailscale antes de tocar nada.
3. **Despliegue en vivo** — stepper + bitácora (terminal translúcida) por SSE.
   Los pasos son **idempotentes**: detectan lo ya instalado y lo marcan hecho,
   así el instalador también sirve como panel de verificación/reparación.
4. **Modo operativo** — credenciales de ArgoCD, port-forward automático,
   confirmación del acceso administrativo y revocación del instalador.

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
- Token temporal obligatorio en toda la API; se revoca al cerrar el handoff.
- El wizard corre como root únicamente dentro de una unidad systemd temporal.
- No se configura `NOPASSWD:ALL`.

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
