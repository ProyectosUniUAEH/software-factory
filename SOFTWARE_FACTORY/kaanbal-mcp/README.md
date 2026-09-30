# MCP de Kaanbal

Conecta tu agente (Claude Code, Codex, Cursor) a **tu** Kaanbal para entender qué
pasa cuando algo falla, reparar recursos autorizados y proponer mejoras mediante
workspaces temporales y pull requests.

Corre en tu máquina y se autentica con tu **token personal**. El agente ve
exactamente lo que tú puedes ver: si el token no trae un permiso, la API dice que
no. Nadie comparte credenciales de la plataforma.

## Instalar

```bash
pip install -r requirements.txt
```

## Crear el token

En la consola: **Acceso → Tokens → + Nuevo token**. Ponle un nombre que diga para
qué es ("MCP de Andrés"), pulsa **Solo lectura (recomendado)** y cópialo: se
muestra una sola vez.

Para sincronizar o reconectar la base, agrega `apps.apps.deploy`. Para contribuir
código, usa el rol `agente-ingeniero` y una concesión de recursos en **Acceso →
Autonomía**. El owner configura esa política confirmando su contraseña.

Cada token permite indicar inicio y fin de vigencia. Un token normal puede no
caducar si se acepta la advertencia. Para comandos en apps/nodos y merge de apps,
marca **Control total para una intervención crítica**, acepta el alcance y
confirma tu usuario y contraseña. Incluye tus permisos actuales y dura como
máximo 24 horas; conserva las restricciones de la política. Los tokens anteriores
no se convierten en críticos. **Revocar** y **Actividad** están en la tabla de tokens.

## Configurar el agente

Claude Code (`~/.claude/mcp.json`) o Codex/Cursor, con la misma forma:

```json
{
  "mcpServers": {
    "kaanbal": {
      "command": "python",
      "args": ["-m", "kaanbal_mcp"],
      "cwd": "C:/ruta/a/software-factory/SOFTWARE_FACTORY/kaanbal-mcp",
      "env": {
        "KAANBAL_URL": "https://kaanbal-api.softwarefactory.site",
        "KAANBAL_TOKEN": "kbl_..."
      }
    }
  }
}
```

Cada quien apunta a la célula que le toca (`kaanbal-api.siboenglishnest.site`
para el laboratorio) con su propio token.

## Qué puede hacer

| Herramienta | Para qué | Permiso |
|---|---|---|
| `list_apps` | Apps con su dominio, URL y estado | `apps.apps.view` |
| `get_app` | Detalle de una app | `apps.apps.view` |
| `app_health` | Salud en ArgoCD por ambiente y último pipeline | `apps.apps.view` |
| `app_logs` | Últimas líneas de log de los pods | `apps.apps.diagnose` |
| `app_env_var_names` | **Nombres** de las variables que recibe la app | `apps.apps.diagnose` |
| `list_domains` | Dominios registrados | `domains.domains.view` |
| `list_stacks` | Catálogo de stacks y últimos lanzamientos | `stacks.catalog.view` |
| `platform_status` | Versión, actualizaciones, salud, Vault | `system.health.view` |
| `activity` | Bitácora: quién hizo qué y cuándo | `logs.records.view` |
| `sync_app` | **Acción**: sincronizar con ArgoCD | `apps.apps.deploy` |
| `repair_db_bindings` | **Acción**: republicar MONGO_URI, DATABASE_URL… | `apps.apps.deploy` |
| `platform_capabilities` | Catálogo vivo con parámetros y permisos | `autonomy.tools.view` |
| `invoke_platform_tool` | Invocar una capacidad descubierta | Permiso de la capacidad + política |
| `platform_upgrade` | Solicitar el Job existente de actualización del core | `core.updates.apply` |
| `platform_upgrade_status` | Consultar el Job de actualización | `core.updates.view` |

## Reparar y contribuir

Primero llama `platform_capabilities`. Las capacidades autorizadas aparecen con
su `input_schema`; se ejecutan mediante `invoke_platform_tool(tool, arguments)`.

- **Reparación:** `execute_app_command` o `execute_node_command`. Requieren token
  crítico, permiso ACL, función habilitada y concesión exacta de app/ambiente o
  nodo. Un comando puede leer credenciales o modificar datos dentro de ese alcance.
- **Cambiar una app:** `open_app_workspace` → consultar `get_workspace` hasta
  `Running` → `initialize_workspace` → `workspace_files` / `write_workspace_file`
  / `run_workspace_command` → `workspace_diff` → `publish_workspace_pr`.
  Envía el digest recibido al publicar. Un token crítico con `autonomy.changes.merge`
  y política de merge puede llamar `merge_app_pr` con el SHA revisado.
- **Mejorar Kaanbal:** inicia con `open_core_workspace`. Publica un PR borrador en
  upstream, desde un fork autorizado si hace falta. El owner revisa e integra en
  GitHub. Después usa `platform_upgrade`, consulta su estado y vuelve a descubrir
  capacidades. El puente puede usar herramientas nuevas del protocolo 1 sin
  reinstalar el cliente MCP.
- **Cerrar:** `close_workspace` elimina el contenedor. También se recoge al vencer
  su vigencia. Un workspace que ya preparó un PR queda congelado para escritura.

La API descarga un snapshot del commit y prepara un Git local para calcular
cambios; esta versión no clona el historial ni entrega la credencial GitHub al
contenedor. Las ramas/commits/PRs se publican mediante la API de GitHub.

El addon de workspaces está aislado de la red; las dependencias necesarias para
validaciones deben estar en la imagen. Los permisos Kubernetes para ejecutar en
apps/nodos necesitan preparación específica del owner. Todo inicia desactivado.

Consulta [activación, límites y MFA](../docs/MCP_AUTONOMY.md).

## Ejemplo

> «El backend de rincon-del-mar está en rojo, ¿por qué?»

El agente encadena `app_health` → `app_logs` → `app_env_var_names`, ve que el
código pide `MONGO_URI` y que la app solo recibe `RINCON_DEL_MAR_BD_URI`, y
propone `repair_db_bindings`. Si su token es de solo lectura, te dice qué hacer
en vez de hacerlo.
