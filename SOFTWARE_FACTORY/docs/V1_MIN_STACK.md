# Stack mínimo v1 — templates y exposición

Actualizado: 2026-07-28

## Estado del catálogo (v4.1)

| Template | ID | Modo | Estado |
|----------|-----|------|--------|
| Vue 3 | `vue3-spa` | scaffold | ✅ smoke OK |
| React | `react-spa` | scaffold | ✅ en catálogo |
| FastAPI | `fastapi-api` | scaffold | ✅ smoke OK |
| MongoDB | `mongodb` | config-only + PVC | ✅ Vault + bindings |
| PostgreSQL | `postgres` | config-only + PVC | ✅ Vault + bindings |
| n8n | `n8n` | config-only + webhooks | ✅ en catálogo |
| EMQX | `emqx` | config-only multi-port | ✅ en catálogo |

### Links seguros (validado 2026-07-28)

**database_bindings (recomendado v1)** — inyecta credenciales desde Vault + DNS interno:

| Relación | Resultado |
|----------|-----------|
| FastAPI ← Postgres (`lab-api-bound` ← `lab-pg`) | `DB_HOST=lab-pg.prod.svc.cluster.local:5432` + user/pass/uri |
| FastAPI ← Mongo (`lab-api-mongo` ← `lab-mongo`) | `MONGO_HOST=lab-mongo.prod.svc.cluster.local:27017` + creds |

Tráfico app→BD = **solo red del cluster** (no sale a internet). Admin a BD = **Tailscale** (`prod-lab-pg.tail….ts.net`).

**ServiceLinks** (`POST /api/v1/links`) — matriz n8n→postgres etc. Crea literales `PG_HOST`…; deployer aún no los escribe al pod (siguiente). Usar bindings del Wizard para v1.

**Exposición BD:** `lab-pg` / `lab-mongo` en dominio público → **404** (correcto).



### Desde consola
1. https://kaanbal-console.softwarefactory.site → Wizard
2. Elige template + entornos + exposición por entorno
3. Deploy → GitHub repo + Actions + ArgoCD

### Desde API (smoke / CI)

```bash
sudo python3 tools/smoke-deploy-fastapi.py
# o manualmente:
TOKEN=...  # POST /api/v1/auth/token
curl -X POST https://kaanbal-api.softwarefactory.site/api/v1/apps \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "name": "api1",
    "template": "fastapi-api",
    "environments": ["dev","staging","prod"],
    "creation_mode": "scaffold",
    "exposure": {
      "type": "public",
      "per_env": {"prod":"public","staging":"public","dev":"tailscale"}
    }
  }'
```

### URLs esperadas
| Env | Público | Tailscale |
|-----|---------|-----------|
| prod | `https://{app}.{domain}` | — |
| staging | `https://staging-{app}.{domain}` | — |
| dev | — | `http://dev-{app}.{tailnet}` |

## Exposición: qué significa cada modo hoy

| Modo | Quién llega | Cómo |
|------|-------------|------|
| **public** | Internet | Cloudflare Tunnel + Ingress Traefik |
| **tailscale** | VPN | Tailscale Operator + MagicDNS |
| **internal** | Solo cluster | ClusterIP + DNS `app.env.svc.cluster.local` — **no es LAN** |
| **both** | Mixto | Tailscale + paths públicos (webhooks) |

## Propuesta: `internal` = LAN (red local)

Hoy `internal` ≠ “accesible en la casa/lab”. Es solo dentro de Kubernetes.
Para v1 proponemos renombrar semántica o añadir modo **`lan`**:

### Opción recomendada (lab / célula única) — NodePort + IP del nodo

1. Al instalar, Kaanbal guarda `cluster_lan_ip` (IP de la interfaz LAN del nodo, ya casi tenemos `cluster_ssh_host` / elastic_ip).
2. Si exposición = `internal`/`lan`:
   - Service → `type: NodePort` (o puerto fijo mapeado)
   - Consola muestra: `http://{cluster_lan_ip}:{nodePort}`
3. Ventajas: sin DNS, sin Cloudflare, sin Tailscale; funciona desde cualquier PC en `192.168.x.x`.
4. La app en la UI copia ese enlace (no el `svc.cluster.local`).

### Alternativa B — Ingress LAN con hostname
- Host: `{app}.lan.{domain}` o `{app}.{lan_ip_dashed}.nip.io`
- Requiere que el router/DNS local apunte al nodo, o usar nip.io.
- Más bonito; más frágil en casas sin DNS.

### Alternativa C — MetalLB
- VIP en la LAN por Service LoadBalancer.
- Overkill para una sola máquina k3s.

**Recomendación v1:** Opción A (NodePort + IP LAN impresa en la consola).
Renombrar UI de “Cluster Only” → “Red local (LAN)” cuando se active.

## Gaps antes de wipe + reinstall

1. Publicar templates actualizados (staging host patches) en `kaanbal-templates`.
2. Añadir al catálogo: `react-spa`, `emqx` (config-only o scaffold mínimo).
3. Enriquecer FastAPI scaffold con `/ws` opcional (`enable_websocket`).
4. Smoke: n8n + emqx + react.
5. Implementar URL LAN para `internal` (NodePort + `cluster_lan_ip`).
6. Luego: reset-local/remote y reinstall desatendido validando el stack mínimo.
