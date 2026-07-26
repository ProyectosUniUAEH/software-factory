"""
Domains Router — multi-dominio (BLUEPRINT RFC-0001 §3.1)
========================================================
De "1 instalación = 1 dominio" a N dominios como entidad de primera clase.
Migración transparente: el dominio guardado por el instalador en system_config
se auto-siembra como Domain default la primera vez que se consulta.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List
from datetime import datetime
from bson import ObjectId
from bson.errors import InvalidId

from app.db import get_db
from app.models import DomainCreate
from app.routers.auth import get_current_active_user

router = APIRouter(dependencies=[Depends(get_current_active_user)])


async def _ensure_seed_default():
    """Si no hay dominios pero el instalador ya fijó uno, sembrarlo como default."""
    db = get_db()
    count = await db.domains.count_documents({})
    if count > 0:
        return
    config = await db.system_config.find_one({"_id": "main"})
    if config and config.get("domain"):
        await db.domains.insert_one({
            "fqdn": config["domain"],
            "cloudflare_zone_id": config.get("cloudflare_zone_id"),
            "tunnel_id": config.get("cloudflare_tunnel_id"),
            "is_default": True,
            "client_id": None,
            "created_at": datetime.utcnow(),
            "seeded_from": "system_config",
        })


@router.get("", response_model=List[dict])
async def list_domains():
    """Listar dominios (siembra el default desde system_config si es la primera vez)"""
    await _ensure_seed_default()
    db = get_db()
    domains = await db.domains.find().to_list(100)
    for domain in domains:
        domain["_id"] = str(domain["_id"])
    return domains


@router.post("", status_code=201)
async def create_domain(domain_data: DomainCreate):
    """Registrar un dominio adicional"""
    await _ensure_seed_default()
    db = get_db()

    existing = await db.domains.find_one({"fqdn": domain_data.fqdn})
    if existing:
        raise HTTPException(status_code=409, detail="Domain already registered")

    # Auto-detectar Zone ID vía Cloudflare si hay token configurado y no se dio
    zone_id = domain_data.cloudflare_zone_id
    if not zone_id:
        config = await db.system_config.find_one({"_id": "main"})
        cf_token = (config or {}).get("cloudflare_token")
        if cf_token:
            import httpx
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(
                        f"https://api.cloudflare.com/client/v4/zones?name={domain_data.fqdn}&status=active",
                        headers={"Authorization": f"Bearer {cf_token}"},
                    )
                    results = resp.json().get("result", [])
                    if results:
                        zone_id = results[0]["id"]
            except Exception:
                pass  # best-effort: el dominio se registra igual, zone se completa después

    total = await db.domains.count_documents({})
    is_default = domain_data.is_default or total == 0
    if is_default:
        await db.domains.update_many({}, {"$set": {"is_default": False}})

    doc = {
        "fqdn": domain_data.fqdn,
        "cloudflare_zone_id": zone_id,
        "tunnel_id": domain_data.tunnel_id,
        "is_default": is_default,
        "client_id": domain_data.client_id,
        "created_at": datetime.utcnow(),
    }
    result = await db.domains.insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    return doc


@router.post("/{domain_id}/set-default")
async def set_default_domain(domain_id: str):
    """Marcar un dominio como default (apps sin domain_id lo usan)"""
    db = get_db()
    try:
        oid = ObjectId(domain_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid domain id")
    domain = await db.domains.find_one({"_id": oid})
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    await db.domains.update_many({}, {"$set": {"is_default": False}})
    await db.domains.update_one({"_id": oid}, {"$set": {"is_default": True}})
    return {"message": f"Domain {domain['fqdn']} is now default"}


@router.get("/{domain_id}/apps")
async def get_domain_apps(domain_id: str):
    """Apps agrupadas bajo este dominio (el default incluye apps sin domain_id)"""
    db = get_db()
    try:
        oid = ObjectId(domain_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid domain id")
    domain = await db.domains.find_one({"_id": oid})
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")

    query = {"domain_id": domain_id}
    if domain.get("is_default"):
        query = {"$or": [{"domain_id": domain_id}, {"domain_id": None}, {"domain_id": {"$exists": False}}]}
    apps = await db.apps.find(query).to_list(200)
    for app in apps:
        app["_id"] = str(app["_id"])
    return apps


@router.delete("/{domain_id}")
async def delete_domain(domain_id: str):
    """Eliminar un dominio (no el default si hay apps o más dominios)"""
    db = get_db()
    try:
        oid = ObjectId(domain_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid domain id")
    domain = await db.domains.find_one({"_id": oid})
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")

    apps_count = await db.apps.count_documents({"domain_id": domain_id})
    if apps_count > 0:
        raise HTTPException(status_code=409, detail=f"{apps_count} app(s) still use this domain")

    total = await db.domains.count_documents({})
    if domain.get("is_default") and total > 1:
        raise HTTPException(status_code=409, detail="Set another domain as default first")

    await db.domains.delete_one({"_id": oid})
    return {"message": f"Domain {domain['fqdn']} deleted"}
