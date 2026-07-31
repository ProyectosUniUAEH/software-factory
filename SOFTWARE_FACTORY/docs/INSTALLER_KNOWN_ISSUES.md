# Kaanbal Installer — Issues conocidos y validaciones

Actualizado: 2026-07-28

Este documento registra fallos encontrados en instalaciones reales del lab
(`softwarefactory.site`) y qué debe hacer el instalador para evitarlos en la
próxima corrida desatendida.

## Resumen ejecutivo

| ID | Síntoma en consola | Causa raíz | Estado fix |
|----|-------------------|------------|------------|
| I-01 | Deploy de app falla al clonar templates | Repo `kaanbal-templates` no existía en GitHub | Corregido: repo + publish en install |
| I-02 | Infrastructure → ArgoCD rojo, 0 apps | API no autentica con ArgoCD (HTTP 307 → HTTPS) | Corregido en `argocd_service.py` |
| I-03 | Vault: Configured NO, Sealed | Vault nunca inicializado en k3s; token no sembrado | Corregido: `bootstrap_vault_lab()` + seed |
| I-04 | Vault job PostSync no corre | Manifiesto asume KMS auto-unseal (AWS); k3s usa Shamir | Documentado; bootstrap manual en lab |
| I-05 | `GITOPS_TOKEN` vs `github_token` en `.env` | Scripts leían solo claves minúsculas | Corregido en `publish-templates*.sh` |
| I-06 | Tailscale operator omitido | ACL sin tag:k8s-operator; instalador no auto-escribía ACL | **Corregido:** `ensure_tailscale_acl_tags()` vía API |
| I-07 | Deploy clona Bitbucket tras seed | `git_username` vacío → deployer default bitbucket | **Corregido:** `_resolve_github_login` + `GITHUB_LOGIN` en env map |
| I-08 | Seed falla `Connection refused :18000` | Port-forward no listo / sin fallback | **Corregido:** wait+ready flag + fallback `https://kaanbal-api.{domain}` |
| I-09 | n8n no conecta a Postgres | Solo `DB_*`; n8n exige `DB_POSTGRESDB_*` | **Corregido:** bindings en `app_deployer` |
| I-10 | n8n OOM / Ingress 502 | 512Mi + Service headless | **Corregido:** 2Gi + `service-http` ClusterIP + Ingress |
| I-11 | React staging kustomize inválido | Regex de patch no toleraba líneas en blanco → mezcla `$patch:delete`+JSON | **Corregido:** `_INGRESS_PATCH_RE` |
| I-12 | Wipe borra `applicationsets` | Cleanup kubectl sin allowlist | **Corregido:** `PROTECTED_ARGOCD_APPS` + wipe script |

---

## I-01 — kaanbal-templates ausente

**Síntoma:** La consola muestra plantillas (catálogo fallback) pero el deploy
termina con:

```text
Failed to clone templates repo
```

**Causa:** El instalador publicaba repos core (`kaanbal-api`, `kaanbal-console`)
pero `kaanbal-templates` era opcional y no existía en el paquete ni en GitHub.

**Fix instalador:**

- Directorio `SOFTWARE_FACTORY/kaanbal-templates/` con `catalog.json` y scaffolds.
- `server.py`: publicar `kaanbal-templates` en el paso repos (obligatorio).
- `unattended.py` preflight: validar fuente local y avisar si falta en GitHub.

**Validación post-install:**

```bash
# Debe devolver 200 con token de org
curl -H "Authorization: token $GITOPS_TOKEN" \
  https://api.github.com/repos/$GITHUB_ORG/kaanbal-templates
```

---

## I-02 — ArgoCD “desconectado” en Infrastructure

**Síntoma:** Overview muestra ArgoCD en rojo, `0 apps | 0 healthy`, aunque
`kubectl get applications -n argocd` lista apps Synced/Healthy.

**Causa:** `kaanbal-api` llamaba a
`http://argocd-server.argocd.svc.cluster.local/api/v1/session` sin seguir el
redirect **307 → HTTPS**. Log: `ArgoCD auth failed: 307`.

**Fix aplicación:**

- `defaults.ARGOCD_SERVER` → `https://argocd-server.argocd.svc.cluster.local:443`
- `argocd_service.py`: `follow_redirects=True` en todos los clientes httpx.

**Fix instalador (`seed_platform`):**

- Sembrar `argocd_password` desde `argocd-initial-admin-secret`.
- Sembrar `argocd_server` explícitamente en `system_config`.

**Validación post-install (HTTP, recomendado):**

```bash
sudo bash tools/verify-platform-api-sudo.sh
# Esperado: connected: True, count > 0, configured: True, sealed: False, RESULT OK
```

Nota: usar `curl` en el script de verificación; `urllib` desde el servidor puede
recibir **403** de Cloudflare sin User-Agent adecuado.

**Validación alternativa (desde pod API):**

```bash
kubectl -n prod exec deploy/kaanbal-api -- \
  python3 -c "import asyncio; from app.services.argocd_service import ArgoCDService; \
  print(asyncio.run(ArgoCDService().get_connection_status()))"
# Esperado: {'connected': True}
```

**Recuperación en cluster ya instalado:** redesplegar imagen de `kaanbal-api`
con el fix y re-sembrar password si hace falta (`tools/fix-platform-seed.sh`).

---

## I-03 — Vault “not configured” / Sealed

**Síntoma:** Infrastructure → Vault: **Configured NO**, **Sealed**, error
`vault_addr/vault_token`.

**Causa:**

1. `seed_platform` no enviaba `vault_token` al API.
2. En k3s, Vault con storage `file` + Shamir **no se auto-inicializa**; el Job
   `vault-auto-init` asume KMS y no corre unseal Shamir.

**Fix instalador:**

- `bootstrap_vault_lab()`: `vault operator init` (1 share) + unseal + secret
  `vault/vault-init-keys`.
- `seed_platform`: incluir `vault_addr` y `vault_token` en `/setup/install`.

**Validación post-install:**

```bash
kubectl -n vault exec deploy/vault -- vault status
# initialized: true, sealed: false

kubectl -n prod exec deploy/kaanbal-api -- \
  curl -s http://vault.vault.svc.cluster.local:8200/v1/sys/health
```

---

## I-04 — Job vault-auto-init vs k3s local

El manifiesto en `infra-gitops/apps/vault/base/vault-auto-init-job.yaml` usa
`recovery_shares` pensado para **auto-unseal con KMS**. En el lab (k3s, sin AWS)
el Job no deja Vault usable.

**Acción:** En perfiles `local` / sin KMS, el instalador usa
`bootstrap_vault_lab()` y no depende del hook PostSync.

**Pendiente v2:** Condicionar el Job con `@kaanbal:if VAULT_KMS` o perfil cloud.

---

## I-05 — Variables de entorno en servidor

En `/etc/kaanbal/installer.env` las claves canónicas son **MAYÚSCULAS**:

- `GITOPS_TOKEN`, `GITHUB_ORG`, `DOCKER_USER`, …

Scripts que solo lean `github_token` fallan silenciosamente. Todos los tools del
instalador deben aceptar ambas formas (como `publish-templates-sudo.sh`).

---

## I-06 — Tailscale operator (ACL tags)

**Síntoma (antes del fix):** Application `tailscale-operator` omitida; apps
`exposure=tailscale` no aparecen en MagicDNS.

**Causa:** El instalador solo *comprobaba* `tag:k8s-operator` y, si faltaba,
omitía el operador pidiendo al usuario editar ACL a mano. El sistema viejo ya
escribía tags vía API (`terraform/tailscale.tf`).

**Fix instalador (2026-07-28):** `ensure_tailscale_acl_tags()` hace GET+POST de
la ACL con el OAuth del usuario, añade `tag:k8s-operator`, `tag:k8s`,
`tag:database`, `tag:iot` preservando `grants`/`ssh`, y luego crea el secret y
declara el operador. **No requiere editar ACL en la consola Tailscale.**

**Requisito del OAuth client:** scopes Policy/ACL (read+write), Devices, Auth Keys.

**Recuperación lab ya instalado:**
```bash
sudo python3 ~/kaanbal-next/tools/ensure-tailscale-in-gitops.py
sudo python3 ~/kaanbal-next/tools/enable-tailscale-lab.py
```


---

## Checklist de validación desatendida (ampliado)

Tras `install.sh --unattended`, además de URLs HTTP 200:

1. **Templates:** repo `kaanbal-templates` en GitHub con al menos un commit.
2. **Deploy smoke:** crear app Vue3 prod desde consola → GitHub repo + Actions OK.
3. **ArgoCD UI en consola:** Infrastructure → Overview → ArgoCD verde, apps > 0.
4. **Vault UI en consola:** Configured YES, Sealed false (o warning documentado).
5. **MongoDB `system_config`:** campos presentes:
   - `git_provider=github`, `github_token`, `github_org`, **`git_username` no vacío**
   - `argocd_password`, `argocd_server`
   - `vault_addr`, `vault_token`
   - `templates_repo=kaanbal-templates`
6. **Catálogo:** `GET /api/v1/templates` incluye `mongodb`, `postgres`, `n8n`, `emqx`.
7. **Smoke mixto (opcional):** mongo/pg (VPN/internal) → n8n/emqx → api con bindings → frontend.
   - BD en dominio público → **404**
   - `DB_HOST` / `MONGO_HOST` = `*.svc.cluster.local`
   - n8n/emqx/api/react públicos → **200** si `exposure=public`

---

## I-07 — Seed sin GitHub login (Bitbucket por defecto)

**Síntoma:** `Failed to clone infra-gitops` contra `bitbucket.org/...` aunque el lab es GitHub.

**Causa:** `seed_platform` solo escribía `git_provider`/`github_*` si `git_username` venía en cfg. El `.env` desatendido no tenía `GITHUB_LOGIN`.

**Fix:** `_resolve_github_login(cfg)` llama a `validate_github` y rellena el login del PAT. `ENV_TO_CONFIG` acepta `GITHUB_LOGIN` / `GITHUB_USER`.

---

## I-08 — Seed vía port-forward frágil

**Síntoma:** `SEED_FAILED HTTP 0: Connection refused` en `:18000`.

**Fix:** `PortForward.ready`; si falla, fallback a `https://kaanbal-api.{domain}`. Tras seed: auth + `templates/refresh`.

---

## I-09 / I-10 — n8n + Postgres / Ingress

**Síntomas:** auth fallida a Postgres; OOM 512Mi; Traefik 502 con Service headless.

**Fix deployer (`_generate_docker_hub_manifests` + bindings):**
- Emitir `DB_TYPE` + `DB_POSTGRESDB_*` cuando el consumer es n8n.
- Resources n8n → 2Gi; env `N8N_LISTEN_ADDRESS=0.0.0.0`.
- Companion Service `{app}-http` ClusterIP + Ingress base para HTTP config-only (sin exigir `health_endpoint`).

---

## I-11 — PatchTransformer staging (React/Vue)

**Síntoma:** `unable to parse SM or JSON patch` mezclando `$patch: delete` con ops JSON.

**Causa:** regex de Ingress patch cortaba en líneas en blanco del overlay.

**Fix:** `_INGRESS_PATCH_RE` tolera blank lines; reemplazo atómico del bloque entero.

---

## I-12 — Wipe de apps de usuario

Nunca borrar Applications ArgoCD: `applicationsets`, `core-config`, `vault`, `tailscale-operator`, `kaanbal-*`.
Ver `PROTECTED_ARGOCD_APPS` y `tools/wipe-and-redeploy-v1-mixed.py`.

---

## Comandos de recuperación rápida (lab)

```bash
# Publicar templates si faltan
sudo bash ~/kaanbal-next/tools/publish-templates-sudo.sh

# Inicializar Vault + re-sembrar API (tras actualizar instalador)
sudo bash ~/kaanbal-next/tools/fix-platform-seed.sh

# Ver apps ArgoCD reales (ground truth)
sudo k3s kubectl -n argocd get applications
```
