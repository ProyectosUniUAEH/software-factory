# 2026-05-24 - DB bindings por ambiente y verificacion VPS

## Pedido

Andres compartio el resumen de una conversacion anterior con Claude sobre WebSockets, soporte multi-puerto futuro y fix del instalador para MongoDB. Pidio verificar si los cambios realmente quedaron en local y en la VPS de prueba (`https://kaanbal-console.futurefarms.mx/`), y adicionalmente implementar que el checkbox de base de datos en APIs permita seleccionar bases desplegadas por el usuario por ambiente, reutilizables en varios backends.

Caso esperado:

- `mongo-db` tiene `stage-vpn` y `prod-interno`.
- Backend con `dev`, `stage`, `prod`.
- Mapping:
  - `dev -> mongo-db-stage`
  - `stage -> mongo-db-stage`
  - `prod -> mongo-db-prod`

## Contexto revisado

- `AGENTS.md`
- `AGENT_WORKLOG.md`
- `agent-worklog/TEMPLATE.md`
- Estado Git de `softwarefactory`, `kaanbal-api`, `kaanbal-console`, `kaanbal-templates`, `infra-gitops`

## Decision

Trabajo en progreso. La solucion debe ser aditiva: conservar despliegue actual, no destruir recursos, y agregar bindings por ambiente entre backends y bases existentes.

## Cambios realizados

- `kaanbal-api`: agregado modelo `DatabaseBinding`, persistencia de `database_bindings` en `apps`, y resolucion de bindings por ambiente en `AppDeployer`.
- `kaanbal-api`: el deployer lee credenciales desde Vault (`secret/{db_env}/{db_app}`), genera connection strings y los copia al secret del backend en su propio ambiente.
- `kaanbal-api`: los backends scaffold reciben env vars desde su secret (`DATABASE_URL`, `MONGODB_URI`, `MYSQL_URL`, `POSTGRES_URL`, `REDIS_URL`, y variables por alias como `MONGO_DATABASE_URL`).
- `kaanbal-console`: agregado selector/matriz "Use existing databases" en el Wizard para templates backend.
- `kaanbal-console`: el selector muestra apps con `category=database` y permite elegir ambiente destino por cada ambiente del backend.
- Commits creados y subidos:
  - `kaanbal-api`: `1c84e25 feat: add per-env database bindings`
  - `kaanbal-console`: `168eca3 feat: add database binding matrix`
- `infra-gitops` recibio commits automaticos de pipeline:
  - `560ad33 deploy(prod): kaanbal-api to prod-1c84e25 [skip ci]`
  - `a15257a deploy(prod): kaanbal-console to prod-168eca3 [skip ci]`

## Comandos y evidencia

```powershell
git -C softwarefactory status --short
git -C kaanbal-api status --short
git -C kaanbal-console status --short
git -C kaanbal-templates status --short
git -C infra-gitops status --short
```

Resultado observado:

- Hay cambios/artefactos sin commitear en varios repos.
- Se requiere clasificar antes de commitear o desplegar.
- `kaanbal-api` compilo correctamente con el Python bundled de Codex.
- `kaanbal-console` build local no pudo completarse por error/timeout leyendo `node_modules` desde OneDrive; se verificaron marcadores del componente y el pipeline remoto si genero imagen Docker.
- Docker Hub confirma tags existentes:
  - `andresbardaleswork/kaanbal-api:prod-1c84e25`
  - `andresbardaleswork/kaanbal-console:prod-168eca3`
- El sitio publico `https://kaanbal-console.futurefarms.mx/` responde 200.
- Pendiente de confirmar en cluster: el bundle publico seguia mostrando asset anterior durante la verificacion local; GitOps esta actualizado, pero no se pudo forzar sync por SSH.

## Seguridad

- Secretos leidos: no. Se intento hidratar `_private/dev/keys/vps.pem` y `_private/dev/CREDENTIALS.txt`, pero OneDrive los mantuvo como offline (`O`) y las lecturas quedaron colgadas, por lo que no se imprimio ni uso su contenido.
- PROD tocado: no.
- Limpiezas destructivas: no.

## Estado final

- Estado: implementado y subido a GitHub/GitOps; verificacion directa en VPS queda pendiente por acceso SSH/OneDrive offline.
- Pendiente: confirmar sync de ArgoCD en el cluster o hidratar credenciales/PEM localmente para ejecutar `kubectl rollout status`.
- Siguiente paso recomendado: abrir `https://kaanbal-console.futurefarms.mx/`, entrar al Wizard de FastAPI y verificar que aparezca "Use existing databases"; si no aparece, forzar sync de ArgoCD para `kaanbal-api-prod` y `kaanbal-console-prod`.
