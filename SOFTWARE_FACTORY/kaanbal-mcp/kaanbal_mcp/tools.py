"""
Herramientas que el agente puede usar sobre Kaanbal
===================================================

Incluye diagnóstico, sincronización y reparación de bindings. El puente de
descubrimiento añade workspaces, PRs, comandos y actualización de la plataforma.
La API aplica ACL, política de recursos y requisitos de token crítico.
Los comandos de reparación pueden acceder a datos sensibles en su alcance.

El esquema de argumentos sale de la firma de cada función en server.py; aquí se
declara para qué sirve cada una y qué permiso necesita el token (la API es quien
manda, esto es para poder explicarlo cuando falta).
"""

from __future__ import annotations

from typing import Any, Dict, List
import re
from urllib.parse import quote

from .client import KaanbalClient, KaanbalError

TOOLS: List[Dict[str, Any]] = [
    {"name": "platform_capabilities", "description": "Descubre las herramientas vigentes de la plataforma, argumentos y permisos. Repetir después de actualizar Kaanbal.", "permission": "autonomy.tools.view"},
    {"name": "invoke_platform_tool", "description": "Ejecuta una herramienta anunciada por platform_capabilities con arguments como objeto JSON. Permite usar herramientas nuevas sin reinstalar este MCP; la API siempre aplica ACL y política.", "permission": "autonomy.tools.view"},
    {"name": "platform_upgrade", "description": "Aplica una actualización de Kaanbal desde upstream tras el merge. Devuelve el Job para consultar el progreso.", "permission": "core.updates.apply"},
    {"name": "platform_upgrade_status", "description": "Consulta el Job de actualización y su log después de reconectar con la API.", "permission": "core.updates.view"},
    {
        "name": "list_apps",
        "description": "Lista las aplicaciones con su dominio, URL pública y estado. Punto de partida para casi todo.",
        "permission": "apps.apps.view",
    },
    {
        "name": "get_app",
        "description": "Detalle de una app: plantilla, ambientes, grupo, dominio y URLs.",
        "permission": "apps.apps.view",
    },
    {
        "name": "app_health",
        "description": (
            "Salud real de una app: estado en ArgoCD por ambiente y resultado del último pipeline. "
            "Lo primero que hay que mirar cuando algo falla."
        ),
        "permission": "apps.apps.view",
    },
    {
        "name": "app_logs",
        "description": (
            "Últimas líneas de log de los pods de una app. Aquí aparece el error concreto: "
            "traceback, variable faltante, imagen que no baja."
        ),
        "permission": "apps.apps.diagnose",
    },
    {
        "name": "app_env_var_names",
        "description": (
            "NOMBRES de las variables de entorno que recibe una app (nunca sus valores). "
            "Sirve para ver si la app pide una variable que nadie le inyecta, que es la causa "
            "más común de que un backend no arranque."
        ),
        "permission": "apps.apps.diagnose",
    },
    {
        "name": "list_domains",
        "description": "Dominios registrados, cuál es el de la instalación y cuántas apps usa cada uno.",
        "permission": "domains.domains.view",
    },
    {
        "name": "list_stacks",
        "description": "Catálogo de stacks disponibles y el estado de los últimos lanzamientos.",
        "permission": "stacks.catalog.view",
    },
    {
        "name": "platform_status",
        "description": "Estado general: versión del core, si hay actualizaciones, salud del sistema y Vault.",
        "permission": "system.health.view",
    },
    {
        "name": "activity",
        "description": (
            "Bitácora reciente: quién hizo qué y cuándo. Útil para saber qué cambió antes de que "
            "algo se rompiera."
        ),
        "permission": "logs.records.view",
    },
    {
        "name": "sync_app",
        "description": "ACCIÓN: pide a ArgoCD que sincronice una app con su manifiesto. Seguro y repetible.",
        "permission": "apps.apps.deploy",
    },
    {
        "name": "repair_db_bindings",
        "description": (
            "ACCIÓN: republica los nombres estándar de la base vinculada (MONGO_URI, DATABASE_URL…) "
            "en una app ya desplegada. Idempotente: si ya los tiene, no cambia nada."
        ),
        "permission": "apps.apps.deploy",
    },
]

TOOLS_BY_NAME = {tool["name"]: tool for tool in TOOLS}


def _app_summary(app: Dict[str, Any]) -> Dict[str, Any]:
    """Una app en pocas líneas: lo que el agente necesita para razonar."""
    domain = app.get("domain") or {}
    return {
        "name": app.get("name"),
        "display_name": app.get("display_name"),
        "template": app.get("template"),
        "group": app.get("app_group"),
        "environments": app.get("environments") or [],
        "status": app.get("status"),
        "is_homepage": bool(app.get("is_root_domain")),
        "domain": domain.get("fqdn"),
        "urls": domain.get("urls") or {},
        "public": bool(domain.get("public")),
        "repo": app.get("repo_url"),
    }


async def call_tool(client: KaanbalClient, name: str, arguments: Dict[str, Any]) -> Any:
    """Ejecutar una herramienta. Devuelve datos ya resumidos, no el volcado crudo."""
    args = arguments or {}

    if name == "platform_capabilities":
        return await client.get("/autonomy/capabilities")

    if name == "invoke_platform_tool":
        catalog = await client.get("/autonomy/capabilities")
        if catalog.get("protocol_version") != 1:
            raise KaanbalError("La API requiere otra versión del puente MCP; actualiza el cliente.")
        spec = next((t for t in catalog.get("tools", []) if t["name"] == args.get("tool")), None)
        if not spec:
            raise KaanbalError("La herramienta no existe o no está concedida al token. Consulta platform_capabilities.")
        values = args.get("arguments") or {}
        if not isinstance(values, dict):
            raise KaanbalError("arguments debe ser un objeto JSON.")
        allowed = set(spec["path_args"] + spec["query_args"] + spec["body_args"])
        if set(values) - allowed or set(spec["required"]) - set(values):
            raise KaanbalError(f"Argumentos inválidos. Admitidos: {sorted(allowed)}; requeridos: {spec['required']}.")
        path = spec["path"]
        if not re.fullmatch(r"/(?:autonomy|core|apps)/[A-Za-z0-9_/{}/-]+", path) or ".." in path or "//" in path:
            raise KaanbalError("El catálogo anunció una ruta no admitida.")
        for key in spec["path_args"]:
            value = str(values[key])
            if not value or value in (".", "..") or "/" in value or "\\" in value:
                raise KaanbalError("Identificador de recurso inválido.")
            path = path.replace("{" + key + "}", quote(value, safe=""))
        if "{" in path or "}" in path or spec["method"] not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
            raise KaanbalError("Contrato de herramienta inválido.")
        query = {k: values[k] for k in spec["query_args"] if k in values}
        body = {k: values[k] for k in spec["body_args"] if k in values}
        return await client.request(spec["method"], path, params=query, **({"json": body} if spec["method"] != "GET" else {}))

    if name == "platform_upgrade":
        return await client.post("/core/upgrade", {"ref": args.get("ref", "main")})

    if name == "platform_upgrade_status":
        return await client.get("/core/upgrade", {"name": args.get("name")})

    if name == "list_apps":
        apps = await client.get("/apps")
        rows = [_app_summary(app) for app in apps]
        if args.get("domain"):
            rows = [row for row in rows if row["domain"] == args["domain"]]
        if args.get("group"):
            rows = [row for row in rows if row["group"] == args["group"]]
        return {"apps": rows, "total": len(rows)}

    if name == "get_app":
        return _app_summary(await client.get(f"/apps/{args['name']}"))

    if name == "app_health":
        data = await client.get(f"/apps/{args['name']}/status/full")
        argocd = data.get("argocd") or {}
        return {
            "app": args["name"],
            "health": (argocd.get("health") or {}).get("status"),
            "synced": argocd.get("isSynced"),
            "per_env": {
                env: {"health": (value or {}).get("health", {}).get("status"), "exists": (value or {}).get("exists")}
                for env, value in (data.get("argocd_per_env") or {}).items()
            },
            "pipeline": (data.get("pipeline") or {}).get("result"),
            "diagnosis": data.get("diagnosis"),
        }

    if name == "app_logs":
        return await client.get(
            f"/apps/{args['name']}/argocd/logs",
            {"env": args.get("env", "prod"), "lines": args.get("lines", 100)},
        )

    if name == "app_env_var_names":
        return await client.get(f"/apps/{args['name']}/env-vars", {"env": args.get("env", "prod")})

    if name == "list_domains":
        domains = await client.get("/domains")
        return {"domains": [
            {
                "fqdn": domain.get("fqdn"),
                "is_default": bool(domain.get("is_default")),
                "status": domain.get("status"),
                "apps": domain.get("apps_count"),
            }
            for domain in domains
        ]}

    if name == "list_stacks":
        catalog = await client.get("/stacks/catalog")
        runs = await client.get("/stacks/runs", {"limit": 5})
        return {"stacks": catalog.get("stacks", []), "recent_runs": runs.get("runs", [])}

    if name == "platform_status":
        version = await client.get("/core/version")
        updates = await client.get("/core/updates")
        health = await client.get("/system/health")
        return {
            "version": version,
            "updates_available": updates.get("available"),
            "pending_commits": len(updates.get("commits") or []),
            "health": health,
        }

    if name == "activity":
        return await client.get("/logs", {"limit": args.get("limit", 25), "category": args.get("category")})

    if name == "sync_app":
        return await client.post(f"/apps/{args['name']}/argocd/sync")

    if name == "repair_db_bindings":
        return await client.post(f"/apps/{args['name']}/bindings/repair")

    raise ValueError(f"Herramienta desconocida: {name}")
