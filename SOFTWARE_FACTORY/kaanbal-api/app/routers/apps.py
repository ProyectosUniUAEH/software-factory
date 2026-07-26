from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse
from typing import List, Any
import asyncio
import json
import re
import logging
from datetime import datetime
from bson import ObjectId

from app.db import get_db
from app.models import AppCreate, App, User, ExposureType
from app.services.app_deployer import AppDeployer
from app.services.pipeline_service import pipeline_service
from app.services.ai_service import ai_service
from app.services.argocd_service import argocd_service
from app.services.activity_log import activity_log, CATEGORY_APP, CATEGORY_DEPLOY, CATEGORY_SYSTEM
from app.defaults import EXPOSURE_RULES, EXPOSURE_RULES_DEFAULT
from app.routers.auth import get_current_active_user

router = APIRouter(dependencies=[Depends(get_current_active_user)])
# Public router for SSE stream - no auth required (EventSource cannot send headers)
stream_router = APIRouter()
logger = logging.getLogger(__name__)

# In-memory event queues for active deploys (app_id -> asyncio.Queue)
_deploy_queues: dict[str, asyncio.Queue] = {}


def _bool_like(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "y"}
    return False


def _is_root_domain_requested(app_data: AppCreate) -> bool:
    cfg = getattr(app_data, "template_config", {}) or {}
    return any(
        _bool_like(cfg.get(k))
        for k in ("use_root_domain", "root_domain", "is_root_app")
    )


def _normalize_app_name(raw_name: str) -> str:
    # Keep Kubernetes-safe slug semantics while being forgiving on input casing/spaces.
    name = (raw_name or "").strip().lower().replace("_", "-")
    name = re.sub(r"\s+", "-", name)
    name = re.sub(r"[^a-z0-9-]", "", name)
    name = re.sub(r"-+", "-", name).strip("-")
    return name


def _normalize_app_group(raw_group: Any) -> str | None:
    group = str(raw_group or "").strip().lower()
    group = re.sub(r"\s+", "-", group)
    group = re.sub(r"[^a-z0-9-_]", "", group)
    group = re.sub(r"-+", "-", group).strip("-")
    return group or None


def _is_valid_app_name(name: str) -> bool:
    if len(name) < 3 or len(name) > 63:
        return False
    return re.match(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$", name) is not None


def _get_env_exposure(app_data: AppCreate, env: str) -> str:
    exposure = app_data.exposure
    if exposure:
        if exposure.port_exposure:
            port_modes = list(exposure.port_exposure.get(env, {}).values())
            if port_modes:
                has_public = "public" in port_modes
                has_tailscale = "tailscale" in port_modes
                if has_public and has_tailscale:
                    return "both"
                if has_public:
                    return "public"
                if has_tailscale:
                    return "tailscale"
                return "internal"
        if exposure.per_env:
            mode = exposure.per_env.get(env)
            return mode.value if hasattr(mode, "value") else str(mode or exposure.type or "internal")
        return exposure.type.value if hasattr(exposure.type, "value") else str(exposure.type or "internal")
    return "internal"


def _build_public_dns_claims(app_data: AppCreate, domain: str, app_name: str, use_root_domain: bool) -> list[str]:
    claims: list[str] = []
    environments = list(dict.fromkeys((getattr(app_data, "environments", None) or []) + ["prod"]))
    for env in environments:
        mode = _get_env_exposure(app_data, env)
        if mode not in ("public", "both"):
            continue
        if env == "prod" and use_root_domain:
            claims.append(domain)
        elif env == "prod":
            claims.append(f"{app_name}.{domain}")
        else:
            claims.append(f"{env}-{app_name}.{domain}")
    # Deduplicate while preserving order
    return list(dict.fromkeys(claims))


def _derive_claims_from_existing_app(app_doc: dict, domain: str) -> list[str]:
    if isinstance(app_doc.get("dns_claims"), list):
        return [str(c).strip().lower() for c in app_doc.get("dns_claims", []) if str(c).strip()]

    name = _normalize_app_name(str(app_doc.get("name") or ""))
    if not name:
        return []

    environments = app_doc.get("environments") or ["prod"]
    exposure = app_doc.get("exposure") or {}
    per_env = exposure.get("per_env") or {}
    mode_default = str(exposure.get("type") or "internal")
    use_root_domain = _bool_like(app_doc.get("is_root_domain"))

    claims: list[str] = []
    for env in environments:
        mode = str(per_env.get(env) or mode_default)
        if mode not in ("public", "both"):
            continue
        if env == "prod" and use_root_domain:
            claims.append(domain)
        elif env == "prod":
            claims.append(f"{name}.{domain}")
        else:
            claims.append(f"{env}-{name}.{domain}")
    return list(dict.fromkeys(claims))


async def _allocate_root_app_name(db) -> str:
    base_name = "homepage"
    candidate = base_name
    suffix = 2
    while await db.apps.find_one({"name": {"$regex": f"^{re.escape(candidate)}$", "$options": "i"}}):
        candidate = f"{base_name}-{suffix}"
        suffix += 1
    return candidate


@router.get("", response_model=List[dict])
async def list_apps():
    """Listar todas las apps"""
    db = get_db()
    apps = await db.apps.find().to_list(100)
    for app in apps:
        app["_id"] = str(app["_id"])
    return apps


@router.get("/{app_name}")
async def get_app(app_name: str):
    """Obtener detalle de una app"""
    db = get_db()
    app = await db.apps.find_one({"name": app_name})
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    app["_id"] = str(app["_id"])
    return app


@router.post("", status_code=202)
async def create_app(
    app_data: AppCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
):
    """
    Crear una nueva app desde template.
    Returns immediately with app_id and stream_url for SSE progress.
    """
    db = get_db()

    config = await db.system_config.find_one({"_id": "main"}, {"domain": 1})
    domain = str((config or {}).get("domain") or "").strip().lower()
    if not domain:
        raise HTTPException(status_code=400, detail="Platform domain is not configured")

    use_root_domain = _is_root_domain_requested(app_data)
    normalized_name = _normalize_app_name(app_data.name)

    # Root-domain apps can omit name in the UI; backend allocates a deterministic internal slug.
    if use_root_domain and not normalized_name:
        normalized_name = await _allocate_root_app_name(db)

    if not _is_valid_app_name(normalized_name):
        raise HTTPException(
            status_code=422,
            detail=(
                "Invalid app name. Use 3-63 chars, lowercase letters, numbers, and hyphens only "
                "(must start/end with alphanumeric)."
            ),
        )

    existing = await db.apps.find_one({"name": {"$regex": f"^{re.escape(normalized_name)}$", "$options": "i"}})
    if existing:
        raise HTTPException(status_code=409, detail=f"App name '{normalized_name}' already exists")

    dns_claims = _build_public_dns_claims(app_data, domain, normalized_name, use_root_domain)
    if dns_claims:
        existing_apps = await db.apps.find({}, {"name": 1, "environments": 1, "exposure": 1, "dns_claims": 1, "is_root_domain": 1}).to_list(500)
        for existing_app in existing_apps:
            existing_claims = _derive_claims_from_existing_app(existing_app, domain)
            overlap = sorted(set(c.lower() for c in dns_claims) & set(c.lower() for c in existing_claims))
            if overlap:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"DNS host already reserved by app '{existing_app.get('name', 'unknown')}': "
                        f"{', '.join(overlap)}"
                    ),
                )

    app_data.name = normalized_name

    # Root-domain apps MUST have prod exposed as public (the root domain IS the public URL).
    if use_root_domain:
        if app_data.exposure.per_env is None:
            app_data.exposure.per_env = {}
        app_data.exposure.per_env["prod"] = ExposureType.PUBLIC

    # Validate exposure modes against category rules
    category = app_data.category
    if category:
        allowed = EXPOSURE_RULES.get(category, EXPOSURE_RULES_DEFAULT)
        if app_data.exposure.per_env:
            for env_name, mode in app_data.exposure.per_env.items():
                if mode.value not in allowed:
                    logger.warning(
                        f"App '{app_data.name}': exposure '{mode.value}' for env '{env_name}' "
                        f"is not recommended for category '{category}'. Allowed: {allowed}"
                    )
        elif app_data.exposure.type.value not in allowed:
            logger.warning(
                f"App '{app_data.name}': exposure '{app_data.exposure.type.value}' "
                f"is not recommended for category '{category}'. Allowed: {allowed}"
            )

    # Crear registro en DB
    app_group = _normalize_app_group(getattr(app_data, "app_group", None))

    app_doc = {
        "name": app_data.name,
        "template": app_data.template,
        "category": app_data.category,
        "app_group": app_group,
        "description": app_data.description,
        "client_id": app_data.client_id,
        "environments": app_data.environments,
        "exposure": app_data.exposure.model_dump(),
        "specs": app_data.specs.model_dump(),
        "is_root_domain": use_root_domain,
        "dns_claims": dns_claims,
        "status": "deploying",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }

    result = await db.apps.insert_one(app_doc)
    app_id = str(result.inserted_id)

    await activity_log.log(
        "app.create.accepted",
        category=CATEGORY_APP,
        actor=current_user.username,
        target=app_data.name,
        detail={
            "template": app_data.template,
            "app_group": app_group,
            "environments": app_data.environments,
            "is_root_domain": use_root_domain,
            "exposure": app_data.exposure.model_dump() if app_data.exposure else None,
        },
    )

    # Create event queue for this deploy
    queue = asyncio.Queue()
    _deploy_queues[app_id] = queue

    # Launch deploy in background
    background_tasks.add_task(_run_deploy, app_id, app_data, queue, current_user.username)

    return {
        "id": app_id,
        "name": app_data.name,
        "status": "deploying",
        "message": "Deployment started",
        "stream_url": f"/api/v1/apps/{app_id}/deploy/stream"
    }


async def _run_deploy(app_id: str, app_data: AppCreate, queue: asyncio.Queue, actor: str = "system"):
    """Background task that runs the deploy and pushes events to the queue."""
    db = get_db()
    deployer = AppDeployer()
    deploy_events = []  # Collect all events for persistent storage
    started_at = datetime.utcnow()

    async def progress_callback(event: dict):
        deploy_events.append(event)
        await activity_log.log(
            f"deploy.{event.get('step', 'progress')}",
            category=CATEGORY_DEPLOY,
            level="error" if event.get("status") == "error" else "info",
            actor=actor,
            target=app_data.name,
            detail={
                "app_id": app_id,
                "template": app_data.template,
                "event": event,
            },
        )
        await queue.put(event)

    try:
        await activity_log.log(
            "deploy.started",
            category=CATEGORY_DEPLOY,
            actor=actor,
            target=app_data.name,
            detail={
                "app_id": app_id,
                "template": app_data.template,
                "environments": getattr(app_data, "environments", []),
            },
        )
        deploy_result = await deployer.deploy(app_data, progress_callback=progress_callback)

        await db.apps.update_one(
            {"_id": ObjectId(app_id)},
            {"$set": {
                "status": "running",
                "repo_url": deploy_result.get("repo_url"),
                "subdomain": deploy_result.get("subdomain"),
                "url": deploy_result.get("url"),
                "connection_info": deploy_result.get("connection_info"),
                "updated_at": datetime.utcnow()
            }}
        )

        await queue.put({
            "step": "complete",
            "message": "Deployment completed successfully!",
            "status": "success",
            "data": deploy_result,
            "done": True
        })
        await activity_log.log(
            "deploy.completed",
            category=CATEGORY_DEPLOY,
            actor=actor,
            target=app_data.name,
            detail={
                "app_id": app_id,
                "repo_url": deploy_result.get("repo_url"),
                "url": deploy_result.get("url"),
                "subdomain": deploy_result.get("subdomain"),
            },
        )

    except Exception as e:
        safe_error = re.sub(r'https://[^@]+@', 'https://***@', str(e))
        logger.error(f"Deploy failed for {app_data.name}: {safe_error}")

        await db.apps.update_one(
            {"_id": ObjectId(app_id)},
            {"$set": {"status": "error", "error": safe_error, "updated_at": datetime.utcnow()}}
        )

        await queue.put({
            "step": "error",
            "message": safe_error,
            "status": "error",
            "done": True
        })
        await activity_log.error(
            "deploy.failed",
            category=CATEGORY_DEPLOY,
            actor=actor,
            target=app_data.name,
            detail={"app_id": app_id, "template": app_data.template, "safe_error": safe_error},
            exc=e,
        )

    finally:
        # Persist deploy log to MongoDB
        try:
            finished_at = datetime.utcnow()
            duration_ms = int((finished_at - started_at).total_seconds() * 1000)
            final_status = deploy_events[-1].get("status") if deploy_events else "unknown"
            # Collect unique environments from events metadata
            envs_seen = list(dict.fromkeys(
                e.get("env") for e in deploy_events if e.get("env")
            ))
            await db.deploy_logs.insert_one({
                "app_id": app_id,
                "app_name": app_data.name,
                "template": app_data.template,
                "environments": envs_seen or getattr(app_data, 'environments', []),
                "exposure": app_data.exposure.dict() if app_data.exposure else None,
                "events": deploy_events,
                "started_at": started_at,
                "finished_at": finished_at,
                "duration_ms": duration_ms,
                "final_status": final_status
            })
        except Exception as log_err:
            logger.error(f"Failed to save deploy log: {log_err}")

        # Keep queue alive briefly so SSE client can read the final event
        await asyncio.sleep(10)
        _deploy_queues.pop(app_id, None)


@stream_router.get("/{app_id}/deploy/stream")
async def stream_deploy_progress(app_id: str):
    """
    SSE endpoint - streams real-time deploy progress events.
    Public: EventSource (browser) cannot send Authorization headers, so auth
    is skipped here. The app_id (MongoDB ObjectId) serves as the access token.
    """
    queue = _deploy_queues.get(app_id)

    if not queue:
        # Deploy already finished or doesn't exist
        db = get_db()
        app = await db.apps.find_one({"_id": ObjectId(app_id)})
        if not app:
            raise HTTPException(status_code=404, detail="App not found")

        async def finished_generator():
            event = {
                "step": "complete",
                "message": f"Deploy already finished (status: {app.get('status', 'unknown')})",
                "status": app.get("status", "unknown"),
                "done": True
            }
            yield f"data: {json.dumps(event)}\n\n"

        return StreamingResponse(
            finished_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
        )

    async def event_generator():
        try:
            while True:
                event = await asyncio.wait_for(queue.get(), timeout=180)
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("done"):
                    break
        except asyncio.TimeoutError:
            yield f"data: {json.dumps({'step': 'timeout', 'message': 'Deploy stream timed out', 'status': 'error', 'done': True})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/{app_name}/deploy-log")
async def get_deploy_log(app_name: str, limit: int = 10):
    """Return the last N deploy logs for an app (most recent first)."""
    db = get_db()
    cursor = db.deploy_logs.find(
        {"app_name": app_name},
        {"events": 0}  # Exclude raw event array from list to keep response light
    ).sort("started_at", -1).limit(limit)
    logs = await cursor.to_list(length=limit)
    for log in logs:
        log["_id"] = str(log["_id"])
    return {"app_name": app_name, "logs": logs}


@router.get("/{app_name}/deploy-log/{log_id}")
async def get_deploy_log_detail(app_name: str, log_id: str):
    """Return a single deploy log with full event stream."""
    from bson import ObjectId as ObjId
    db = get_db()
    if not ObjId.is_valid(log_id):
        raise HTTPException(status_code=400, detail="Invalid log id")
    log = await db.deploy_logs.find_one({"_id": ObjId(log_id), "app_name": app_name})
    if not log:
        raise HTTPException(status_code=404, detail="Deploy log not found")
    log["_id"] = str(log["_id"])
    return log


# Core apps that cannot be deleted — they are part of the platform infrastructure
CORE_APP_NAMES = {"datastore", "kaanbal-api", "kaanbal-console", "vault", "tailscale-operator"}


@router.delete("/{app_id}")
async def delete_app(app_id: str, current_user: User = Depends(get_current_active_user)):
    """Eliminar una app y todos sus recursos"""
    db = get_db()

    if not ObjectId.is_valid(app_id):
        raise HTTPException(status_code=400, detail="Invalid app id")

    app = await db.apps.find_one({"_id": ObjectId(app_id)})
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    # Prevent deletion of core infrastructure apps
    if app.get("name") in CORE_APP_NAMES:
        raise HTTPException(
            status_code=403,
            detail=f"Cannot delete core infrastructure app '{app['name']}'. This app is required by the platform."
        )

    # Eliminar recursos externos
    deployer = AppDeployer()
    cleanup_report = {}
    try:
        cleanup_report = await deployer.delete_app(app["name"], app.get("environments", []))
    except Exception as e:
        logger.warning(f"Error cleaning up resources for {app.get('name')}: {e}")
        # Continuamos para eliminar de DB aunque falle cleanup

    # Eliminar de DB
    await db.apps.delete_one({"_id": ObjectId(app_id)})

    # Limpiar referencias de apps de prueba en templates custom
    await db.custom_templates.update_many(
        {},
        {"$pull": {"test_apps": {"app_name": app["name"]}}}
    )

    await activity_log.log(
        "app.deleted",
        category=CATEGORY_APP,
        actor=current_user.username,
        target=app["name"],
        detail={"cleanup": cleanup_report, "app_id": app_id},
    )

    return {
        "status": "success",
        "message": f"App {app['name']} deleted",
        "cleanup": cleanup_report
    }


@router.post("/maintenance/cleanup-orphans")
async def cleanup_orphan_artifacts(dry_run: bool = False, current_user: User = Depends(get_current_active_user)):
    """Limpia secretos huérfanos en Vault que no pertenecen a apps activas en Mongo."""
    db = get_db()
    app_docs = await db.apps.find({}, {"name": 1, "environments": 1}).to_list(300)

    active_apps = {doc.get("name") for doc in app_docs if doc.get("name")}
    envs = {"dev", "staging", "prod"}
    for doc in app_docs:
        for env in doc.get("environments", []) or []:
            envs.add(env)

    deployer = AppDeployer()
    report = await deployer.cleanup_orphan_vault_secrets(active_apps, sorted(envs), dry_run=dry_run)

    await activity_log.log(
        "maintenance.cleanup_orphans",
        category=CATEGORY_SYSTEM,
        actor=current_user.username,
        detail={"dry_run": dry_run, "report": report},
    )

    return {
        "status": "success",
        "dry_run": dry_run,
        "active_apps": sorted(active_apps),
        "report": report
    }


@router.post("/maintenance/cleanup-tailscale")
async def cleanup_orphan_tailscale_devices(dry_run: bool = True, current_user: User = Depends(get_current_active_user)):
    """Limpia dispositivos Tailscale huérfanos que no pertenecen a apps activas en Mongo."""
    db = get_db()
    app_docs = await db.apps.find({}, {"name": 1, "environments": 1}).to_list(300)

    active_apps = {doc.get("name") for doc in app_docs if doc.get("name")}
    envs = {"dev", "staging", "prod"}
    for doc in app_docs:
        for env in doc.get("environments", []) or []:
            envs.add(env)

    deployer = AppDeployer()
    report = await deployer.cleanup_orphan_tailscale_devices(active_apps, sorted(envs), dry_run=dry_run)

    await activity_log.log(
        "maintenance.cleanup_tailscale",
        category=CATEGORY_SYSTEM,
        actor=current_user.username,
        detail={"dry_run": dry_run, "report": report},
    )

    return {
        "status": "success",
        "dry_run": dry_run,
        "active_apps": sorted(active_apps),
        "report": report
    }


@router.get("/{app_name}/pipeline")
async def get_app_pipeline_status(app_name: str):
    """Obtener estado del pipeline de una app"""
    db = get_db()
    app = await db.apps.find_one({"name": app_name})
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    
    # Obtener estado del pipeline
    pipeline_status = await pipeline_service.get_pipeline_status(app_name)
    
    # Generar resumen con IA
    summary = await ai_service.get_app_status_summary(app, pipeline_status)
    
    return {
        "app_name": app_name,
        "app_status": app.get("status"),
        "pipeline": pipeline_status,
        "ai_summary": summary
    }


@router.get("/{app_name}/pipeline/logs")
async def get_app_pipeline_logs(app_name: str):
    """Obtener logs detallados del pipeline"""
    logs = await pipeline_service.get_pipeline_logs(app_name)
    return logs


@router.get("/{app_name}/pipeline/history")
async def get_app_pipeline_history(app_name: str, limit: int = 5):
    """Obtener historial de pipelines"""
    history = await pipeline_service.get_all_pipelines(app_name, limit)
    return {"pipelines": history}


@router.post("/{app_name}/analyze")
async def analyze_app_error(app_name: str):
    """
    Analizar error de una app con IA.
    Ahora incluye contexto completo: info del pipeline, logs extensos.
    """
    db = get_db()
    app = await db.apps.find_one({"name": app_name})
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    
    # Obtener logs del pipeline con más contexto
    logs_data = await pipeline_service.get_pipeline_logs(app_name, include_all_logs=False)
    
    # Extraer info del pipeline para contexto
    pipeline_info = logs_data.get("pipeline_info", {})
    
    # Extraer logs de steps fallidos (ahora con 6000 chars por step)
    failed_logs = ""
    for step in logs_data.get("steps", []):
        if step.get("result") == "FAILED" and step.get("logs"):
            total_chars = step.get("logs_total_chars", len(step.get("logs", "")))
            failed_logs += f"\n\n=== Step: {step['name']} ===\n"
            failed_logs += f"(Total log: {total_chars} chars, showing last portion)\n\n"
            failed_logs += step['logs']
    
    error_message = app.get("error", "Unknown error")
    
    # Analizar con IA - ahora con más contexto
    analysis = await ai_service.analyze_pipeline_error(
        app_name=app_name,
        pipeline_logs=failed_logs,
        error_message=error_message,
        pipeline_info=pipeline_info
    )
    
    return {
        "app_name": app_name,
        "pipeline_info": pipeline_info,
        "logs_analyzed_chars": len(failed_logs),
        "analysis": analysis
    }


# =============================================================================
# ArgoCD Integration - Real Runtime Status
# =============================================================================

@router.get("/{app_name}/argocd")
async def get_app_argocd_status(app_name: str):
    """
    Obtener estado real de la app desde ArgoCD.
    Retorna health, sync status, condiciones y recursos.
    """
    status = await argocd_service.get_application_status(app_name)
    
    if status is None:
        return {
            "error": "ArgoCD not configured or unreachable",
            "exists": False
        }
    
    return status


@router.get("/{app_name}/argocd/resources")
async def get_app_argocd_resources(app_name: str):
    """
    Obtener árbol de recursos (pods, deployments, services) de ArgoCD.
    """
    resources = await argocd_service.get_resource_tree(app_name)
    
    if resources is None:
        return {"error": "Could not fetch resource tree"}
    
    return resources


@router.post("/{app_name}/argocd/sync")
async def sync_app_argocd(app_name: str):
    """
    Forzar sincronización de la app en ArgoCD.
    Útil cuando el pipeline pasó pero no se aplicaron los cambios.
    """
    result = await argocd_service.sync_application(app_name)
    return result


@router.get("/argocd/all")
async def list_argocd_apps():
    """
    Listar todas las apps en ArgoCD con estado de cada una.
    Útil para comparar con apps en Kaanbal DB y ver estado general.
    """
    conn = await argocd_service.get_connection_status()
    apps = await argocd_service.list_applications() if conn.get("connected") else []
    db = get_db()
    kaanbal_apps_count = await db.apps.count_documents({})
    
    # Calcular estadísticas
    healthy = sum(1 for a in apps if a.get("isHealthy"))
    degraded = sum(1 for a in apps if a.get("health") == "Degraded")
    synced = sum(1 for a in apps if a.get("isSynced"))
    
    return {
        "apps": apps,
        "count": len(apps),
        "connected": conn.get("connected", False),
        "connection_reason": conn.get("reason", ""),
        "kaanbal_apps_count": kaanbal_apps_count,
        "stats": {
            "healthy": healthy,
            "degraded": degraded,
            "synced": synced,
            "outOfSync": len(apps) - synced
        }
    }


@router.get("/{app_name}/argocd/logs")
async def get_app_argocd_logs(app_name: str, pod_name: str = None):
    """
    Obtener logs de pods de la app desde ArgoCD.
    Útil para debuggear problemas de runtime.
    """
    result = await argocd_service.get_app_logs(app_name, pod_name)
    return result


@router.get("/{app_name}/status/full")
async def get_app_full_status(app_name: str):
    """
    Obtener estado COMPLETO y REAL de una app:
    - Estado en Kaanbal DB
    - Estado del pipeline en Bitbucket  
    - Estado real en ArgoCD (health, sync, pods, images)
    - Diagnóstico automático del problema
    """
    db = get_db()
    
    # 1. Estado en DB
    app = await db.apps.find_one({"name": app_name})
    if not app:
        raise HTTPException(status_code=404, detail="App not found in Kaanbal")
    
    app["_id"] = str(app["_id"])
    
    # 2. Estado del pipeline
    pipeline_status = await pipeline_service.get_pipeline_status(app_name)
    
    # 3. Estado en ArgoCD (detallado)
    argocd_status = await argocd_service.get_application_status(app_name)

    # 3b. Estado por environment (cada env tiene su propia ArgoCD app)
    environments = app.get("environments", ["prod"])
    argocd_per_env = await argocd_service.get_multi_env_status(app_name, environments)

    # 4. Árbol de recursos para diagnóstico
    resource_tree = None
    if argocd_status and argocd_status.get("exists"):
        resource_tree = await argocd_service.get_resource_tree(app_name)

    # 5. Determinar estado real y diagnóstico
    real_status, diagnosis = _diagnose_app_status(app, pipeline_status, argocd_status, resource_tree)

    return {
        "app": app,
        "pipeline": pipeline_status,
        "argocd": argocd_status,
        "argocd_per_env": argocd_per_env,
        "resources": resource_tree,
        "realStatus": real_status,
        "diagnosis": diagnosis,
        "summary": _generate_status_summary(app, pipeline_status, argocd_status, resource_tree)
    }


def _diagnose_app_status(app: dict, pipeline: dict, argocd: dict, resources: dict) -> tuple:
    """
    Diagnostica el estado real de la app y genera mensaje explicativo.
    Retorna (status, diagnosis)
    """
    diagnosis = {
        "status": "unknown",
        "message": "",
        "issues": [],
        "recommendations": []
    }
    
    # Si no existe en ArgoCD
    if not argocd or not argocd.get("exists"):
        if pipeline.get("result") == "FAILED":
            diagnosis["status"] = "build_failed"
            diagnosis["message"] = "El pipeline falló, la imagen no se construyó"
            diagnosis["issues"].append("Pipeline build failed")
            diagnosis["recommendations"].append("Revisa los logs del pipeline para ver el error")
            return "error", diagnosis
        elif pipeline.get("state") == "IN_PROGRESS":
            diagnosis["status"] = "building"
            diagnosis["message"] = "Pipeline en progreso, esperando build"
            return "building", diagnosis
        else:
            diagnosis["status"] = "not_deployed"
            diagnosis["message"] = "App no encontrada en ArgoCD"
            diagnosis["recommendations"].append("Verifica que los manifests existen en infra-gitops/apps/")
            return "not_deployed", diagnosis
    
    # Existe en ArgoCD - revisar health
    health_status = argocd.get("health", {}).get("status", "Unknown")
    sync_status = argocd.get("sync", {}).get("status", "Unknown")
    
    if health_status == "Healthy" and sync_status == "Synced":
        diagnosis["status"] = "healthy"
        diagnosis["message"] = "App corriendo correctamente"
        return "running", diagnosis
    
    if health_status == "Progressing":
        diagnosis["status"] = "deploying"
        diagnosis["message"] = "Deployment en progreso"
        return "deploying", diagnosis
    
    if health_status == "Degraded":
        diagnosis["status"] = "degraded"
        
        # Analizar recursos para encontrar el problema
        if resources:
            for pod in resources.get("pods", []):
                if pod.get("health") == "Degraded":
                    msg = pod.get("healthMessage", "")
                    diagnosis["issues"].append(f"Pod {pod['name']}: {msg}")
                    
                    # Diagnóstico específico
                    if "Back-off pulling image" in msg:
                        diagnosis["message"] = "Error al descargar imagen de Docker Hub"
                        diagnosis["recommendations"].append("Verifica que el pipeline haya construido la imagen")
                        diagnosis["recommendations"].append("Verifica credenciales de Docker Hub")
                    elif "CrashLoopBackOff" in msg:
                        diagnosis["message"] = "La app está crasheando al iniciar"
                        diagnosis["recommendations"].append("Revisa los logs del pod para ver el error")
                    elif "ImagePullBackOff" in msg:
                        diagnosis["message"] = "No se puede descargar la imagen"
                        diagnosis["recommendations"].append("La imagen puede no existir en Docker Hub")
            
            for dep in resources.get("deployments", []):
                if dep.get("health") == "Degraded":
                    msg = dep.get("healthMessage", "")
                    if "exceeded its progress deadline" in msg:
                        diagnosis["issues"].append("Deployment timeout - pods no inician")
        
        if not diagnosis["message"]:
            diagnosis["message"] = argocd.get("health", {}).get("message", "App degradada")
        
        return "error", diagnosis
    
    if sync_status == "OutOfSync":
        diagnosis["status"] = "out_of_sync"
        diagnosis["message"] = "Cambios pendientes de sincronizar"
        diagnosis["recommendations"].append("Ejecuta un sync manual o espera el auto-sync")
        return "out_of_sync", diagnosis
    
    diagnosis["message"] = f"Estado: {health_status} / {sync_status}"
    return "unknown", diagnosis


def _generate_status_summary(app: dict, pipeline: dict, argocd: dict, resources: dict = None) -> str:
    """Genera resumen legible del estado para mostrar en UI"""
    p_result = pipeline.get("result")
    
    if argocd and argocd.get("exists"):
        health = argocd.get("health", {}).get("status", "Unknown")
        sync = argocd.get("sync", {}).get("status", "Unknown")
        
        if health == "Healthy" and sync == "Synced":
            return "✅ Running - All systems healthy"
        elif health == "Progressing":
            return "🔄 Deploying - Pods starting up"
        elif health == "Degraded":
            # Buscar mensaje específico
            if resources:
                for pod in resources.get("pods", []):
                    if pod.get("health") == "Degraded":
                        msg = pod.get("healthMessage", "")
                        if "Back-off pulling image" in msg:
                            return "❌ Image pull error - Check Docker Hub"
                        elif "CrashLoopBackOff" in msg:
                            return "❌ App crashing - Check logs"
            return "❌ Degraded - Check pod status"
        elif sync == "OutOfSync":
            return "⚠️ Out of sync - Changes pending"
        else:
            return f"⚠️ {health} / {sync}"
    
    elif p_result == "FAILED":
        return "❌ Build failed - Check pipeline logs"
    elif p_result == "SUCCESSFUL":
        return "⚠️ Build passed but not synced to ArgoCD"
    elif pipeline.get("state") == "IN_PROGRESS":
        return "🔄 Building..."
    
    return f"Status: {app.get('status', 'unknown')}"


@router.post("/{app_name}/refresh-status")
async def refresh_app_status(app_name: str, current_user: User = Depends(get_current_active_user)):
    """
    Refresh and sync the app's pipeline/ArgoCD status to the database.
    
    This endpoint:
    1. Checks Bitbucket for latest pipeline status
    2. Checks ArgoCD for deployment health
    3. Updates the app record in MongoDB with current state
    4. Returns the updated status
    """
    db = get_db()
    
    app = await db.apps.find_one({"name": app_name})
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    
    # Get pipeline status
    pipeline = await pipeline_service.get_pipeline_status(app_name)
    
    # Get ArgoCD status
    argocd = await argocd_service.get_application_status(app_name)
    
    # Determine new status based on real state
    new_status = _compute_app_status(pipeline, argocd)
    
    # Update in DB
    update_data = {
        "status": new_status,
        "last_pipeline_status": pipeline.get("result"),
        "last_pipeline_build": pipeline.get("build_number"),
        "last_pipeline_at": datetime.utcnow() if pipeline.get("build_number") else None,
        "updated_at": datetime.utcnow()
    }
    
    await db.apps.update_one(
        {"name": app_name},
        {"$set": update_data}
    )

    await activity_log.log(
        "app.status.refreshed",
        category=CATEGORY_APP,
        actor=current_user.username,
        target=app_name,
        detail={
            "previous_status": app.get("status"),
            "new_status": new_status,
            "pipeline": {
                "state": pipeline.get("state"),
                "result": pipeline.get("result"),
                "build_number": pipeline.get("build_number"),
            },
            "argocd": {
                "exists": argocd.get("exists") if argocd else False,
                "health": argocd.get("health", {}).get("status") if argocd else None,
                "sync": argocd.get("sync", {}).get("status") if argocd else None,
            },
        },
    )
    
    return {
        "app_name": app_name,
        "previous_status": app.get("status"),
        "new_status": new_status,
        "pipeline": {
            "state": pipeline.get("state"),
            "result": pipeline.get("result"),
            "build_number": pipeline.get("build_number")
        },
        "argocd": {
            "exists": argocd.get("exists") if argocd else False,
            "health": argocd.get("health", {}).get("status") if argocd else None,
            "sync": argocd.get("sync", {}).get("status") if argocd else None
        }
    }


def _compute_app_status(pipeline: dict, argocd: dict) -> str:
    """
    Compute the app status based on pipeline and ArgoCD state.
    Maps to our new AppStatus enum.
    """
    pipeline_state = pipeline.get("state")
    pipeline_result = pipeline.get("result")
    
    # If ArgoCD exists and is healthy, app is running
    if argocd and argocd.get("exists"):
        health = argocd.get("health", {}).get("status")
        sync = argocd.get("sync", {}).get("status")
        
        if health == "Healthy" and sync == "Synced":
            return "healthy"
        elif health == "Progressing":
            return "deploying"
        elif health == "Degraded":
            return "degraded"
        elif sync == "OutOfSync":
            return "deploying"
        else:
            return "degraded"
    
    # No ArgoCD, check pipeline
    if pipeline_state == "IN_PROGRESS":
        return "pipeline_running"
    elif pipeline_result == "FAILED":
        return "pipeline_failed"
    elif pipeline_result == "SUCCESSFUL":
        return "image_ready"  # Built but not deployed yet
    
    # No pipeline info, check if repo exists
    if pipeline.get("build_number"):
        return "awaiting_code"
    
    return "created"


@router.get("/{app_name}/repo-status")
async def get_repo_status(app_name: str):
    """
    Get the current status of the app's Bitbucket repository.
    
    Returns:
    - repo_exists: Whether the repo exists
    - has_code: Whether there's code in main branch
    - last_commit: Info about the last commit
    - branches: List of branches
    - pipeline_enabled: Whether pipelines are enabled
    """
    # Check if repo exists and has content
    status = await pipeline_service.get_repo_status(app_name)
    return status


@router.get("/{app_name}/tailscale-tags")
async def get_tailscale_tags(app_name: str):
    """Get current Tailscale ACL tags for an app."""
    db = get_db()
    app = await db.apps.find_one({"name": app_name}, {"tailscale_tags": 1})
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    return {"tags": app.get("tailscale_tags", ["tag:k8s"])}


@router.patch("/{app_name}/group")
async def update_app_group(app_name: str, body: dict, current_user: User = Depends(get_current_active_user)):
    """Update or clear a logical app group used by console/dashboard organization."""
    db = get_db()
    app = await db.apps.find_one({"name": app_name}, {"name": 1, "app_group": 1})
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    normalized_group = _normalize_app_group(body.get("app_group"))

    await db.apps.update_one(
        {"name": app_name},
        {"$set": {"app_group": normalized_group, "updated_at": datetime.utcnow()}},
    )

    await activity_log.log(
        "app.group.updated",
        category=CATEGORY_APP,
        actor=current_user.username,
        target=app_name,
        detail={"app_group": normalized_group},
    )

    return {
        "name": app_name,
        "app_group": normalized_group,
        "message": "Group updated" if normalized_group else "Group cleared",
    }


@router.patch("/{app_name}/tailscale-tags")
async def update_tailscale_tags(app_name: str, body: dict, current_user: User = Depends(get_current_active_user)):
    """
    Update Tailscale ACL tags for an app.
    Tags control who on the Tailnet can access this service.
    
    Body: { "tags": ["tag:k8s", "tag:database", "tag:team-alpha"] }
    
    - Updates tags in MongoDB
    - Applies tags to running K8s Services via K8s API (immediate effect)
    """
    db = get_db()
    app = await db.apps.find_one({"name": app_name})
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    tags = body.get("tags", [])
    # Validate tag format: must start with "tag:"
    for t in tags:
        if not t.startswith("tag:"):
            raise HTTPException(status_code=400, detail=f"Invalid tag '{t}'. Tags must start with 'tag:'")

    # Save to MongoDB
    await db.apps.update_one(
        {"name": app_name},
        {"$set": {"tailscale_tags": tags, "updated_at": datetime.utcnow()}}
    )

    await activity_log.log(
        "app.tailscale_tags.updated",
        category=CATEGORY_APP,
        actor=current_user.username,
        target=app_name,
        detail={"tags": tags},
    )

    # Apply tags to running K8s Services via K8s API (pod runs inside the cluster)
    environments = app.get("environments", ["dev", "staging", "prod"])
    tags_csv = ",".join(tags) if tags else "tag:k8s"
    applied_envs = []

    try:
        import httpx
        import ssl
        # K8s API is at https://kubernetes.default.svc with service account token
        k8s_host = "https://kubernetes.default.svc"
        sa_token_path = "/var/run/secrets/kubernetes.io/serviceaccount/token"
        ca_path = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"

        import os
        if os.path.exists(sa_token_path):
            with open(sa_token_path) as f:
                token = f.read().strip()

            ssl_ctx = ssl.create_default_context(cafile=ca_path) if os.path.exists(ca_path) else False

            async with httpx.AsyncClient(base_url=k8s_host, verify=ssl_ctx, timeout=10) as client:
                headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/merge-patch+json"}
                for env in environments:
                    svc_name = f"{app_name}-ts"
                    patch_body = {"metadata": {"annotations": {"tailscale.com/tags": tags_csv}}}
                    try:
                        resp = await client.patch(
                            f"/api/v1/namespaces/{env}/services/{svc_name}",
                            headers=headers,
                            json=patch_body
                        )
                        if resp.status_code == 200:
                            applied_envs.append(env)
                        else:
                            logger.warning(f"K8s patch for {env}/{svc_name}: HTTP {resp.status_code}")
                    except Exception as e:
                        logger.warning(f"Failed to patch {env}/{svc_name}: {e}")
        else:
            logger.info("Not running inside K8s cluster — tags saved to DB only")
    except Exception as e:
        logger.warning(f"K8s API tag application failed: {e}")

    return {
        "tags": tags,
        "applied_to_cluster": applied_envs,
        "note": "Tags updated. Configure Tailscale ACL policy to enforce access rules based on these tags."
    }
