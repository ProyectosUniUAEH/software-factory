# Bitácora lab Kaanbal — softwarefactory.site

Registro operativo para aprender de errores **antes** de la reinstalación desatendida final.
Formato: fecha UTC-6 | acción | resultado | aprendizaje → instalador

---

## 2026-07-28 — Sesión: arreglar cluster ya instalado (sin reinstall)

### Contexto
- Core URLs OK (consola, API, ArgoCD público, agente).
- App `test2` desplegada: GitHub Actions OK, ArgoCD Synced/Healthy.
- UI Infrastructure: ArgoCD rojo (0 apps), Vault not configured.

### Hallazgos previos (ver INSTALLER_KNOWN_ISSUES.md)
| ID | Problema | Fix en código |
|----|----------|---------------|
| I-01 | kaanbal-templates faltaba | Repo publicado |
| I-02 | ArgoCD auth HTTP→307 | argocd_service HTTPS + follow_redirects |
| I-03 | Vault sin token en MongoDB | bootstrap_vault_lab + seed_platform |

---

### 2026-07-28 ~23:05 — repair-lab en background

**Comando:** `nohup sudo bash ~/kaanbal-next/tools/repair-lab.sh >> logs/repair-lab.log 2>&1 &`

**Log:** `~/kaanbal-next/logs/repair-lab-20260728-050434.log`

| Paso | Acción | Resultado |
|------|--------|-----------|
| 1 | `fix-platform-seed.sh` | OK — Vault desbloqueado, config sembrada |
| 2 | Push `kaanbal-api` + Kaniko build | OK — imagen `denissesoftwarefactory/kaanbal-api:prod-fbea313` |
| 2b | Push `infra-gitops` tag | Everything up-to-date (tag ya aplicado en cluster) |
| 3 | Rollout `kaanbal-api` | OK — `successfully rolled out` |
| 4 | Verificaciones | **FALLÓ parcial** — bug `xargs -I{} log` (log es función bash, no binario) |

**Aprendizaje → instalador (I-07):** no usar `xargs` con funciones bash en scripts de
verificación; usar variables + `log "..."` o script Python dedicado.

---

### 2026-07-28 ~23:15 — Verificación post-repair

**Comando:** `sudo bash /tmp/verify-platform-api-sudo.sh` (credenciales desde `/etc/kaanbal/installer.env`)

```
=== ArgoCD ===
connected: True
count: 10
=== Vault ===
configured: True
sealed: False
reachable: True
=== RESULT ===
OK
```

**Ground truth kubectl:** 10 applications en namespace `argocd`.

**Estado UI esperado:** Infrastructure → ArgoCD verde, Vault configured (hard refresh).

---

### Errores operativos recurrentes (lab)

| Problema | Causa | Solución |
|----------|-------|----------|
| `set: pipefail\r: invalid option` | CRLF en scripts copiados desde Windows | `normalize-sh.py` en servidor antes de ejecutar |
| PowerShell rompe heredocs/`$(...)` en SSH | Escaping local | Scripts `.sh`/`.py` en `/tmp`, SSH con comillas simples externas |
| `urllib` → HTTP 403 en auth API | Cloudflare / sin User-Agent | Verificar con `curl` (script `verify-platform-api.py` usa subprocess curl) |
| `grep installer.env` permission denied | Archivo root-only | Wrapper `verify-platform-api-sudo.sh` con `source` tras `sudo` |

---

### Fixes aplicados en repo (esta sesión)

- `tools/repair-lab.sh` — paso 4: quitar `xargs log`, integrar `verify-platform-api-sudo.sh`
- `tools/verify-platform-api.py` — verificación HTTP vía curl (no urllib)
- `tools/verify-platform-api-sudo.sh` — lee `KAANBAL_ADMIN_*` de installer.env

---

### Pendiente antes de reinstall desatendida

- [x] Catálogo v4.1: react, postgres, emqx + mongo/n8n enriquecidos
- [x] Smoke Mongo + Postgres: StatefulSet + Vault keys OK (`lab-mongo`, `lab-pg`)
- [ ] Smoke n8n + emqx + react-spa
- [ ] Implementar URL LAN para `internal` (NodePort + IP nodo)
- [ ] Wipe + reinstall desatendido con stack mínimo

---

### Comandos útiles

```bash
# Verificar plataforma (en servidor)
sudo bash ~/kaanbal-next/tools/verify-platform-api-sudo.sh

# Logs repair
tail -f ~/kaanbal-next/logs/repair-lab-*.log

# Re-sembrar si hace falta
sudo bash ~/kaanbal-next/tools/fix-platform-seed.sh

# ArgoCD ground truth
sudo k3s kubectl -n argocd get applications
```
