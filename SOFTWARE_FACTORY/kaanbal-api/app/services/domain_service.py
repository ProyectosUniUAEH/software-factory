"""
Domain Service — multi-dominio (BLUEPRINT RFC-0001 §3.1)
=======================================================
Resuelve el dominio efectivo de una app y provisiona dominios adicionales en
Cloudflare.

El instalador deja un solo dominio cableado de punta a punta: un tunel con
reglas `*.dominio -> Traefik`, DNS wildcard + raiz apuntando a
`<tunnel>.cfargotunnel.com` y el zone_id guardado en `system_config`. Registrar
un segundo dominio exige repetir ese cableado, no solo insertar el documento:
por eso `provision()` **agrega** reglas al tunel existente en lugar de
sobrescribir su configuracion.
"""

import logging
from typing import Any, Dict, List, Optional

import httpx

from app.db import get_db

logger = logging.getLogger(__name__)

CF_API = "https://api.cloudflare.com/client/v4"
TRAEFIK_SERVICE = "http://traefik.kube-system.svc.cluster.local:80"


class DomainError(Exception):
    """Fallo de validacion o provision de un dominio."""


def _headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _check(check_id: str, label: str, status: str, detail: str = "") -> Dict[str, str]:
    """Un renglon del reporte de validacion que consume la UI."""
    return {"id": check_id, "label": label, "status": status, "detail": detail}


async def get_system_config() -> Dict[str, Any]:
    db = get_db()
    return await db.system_config.find_one({"_id": "main"}) or {}


async def resolve_for_app(app_doc: Optional[dict]) -> Dict[str, Any]:
    """Dominio efectivo de una app: su domain_id, si no el default, si no el del instalador.

    Devuelve siempre un dict con fqdn/zone_id/tunnel_id para que el deployer
    pueda operar aunque la coleccion `domains` todavia no exista (instalaciones
    anteriores a multi-dominio).
    """
    db = get_db()
    config = await get_system_config()
    fallback = {
        "fqdn": config.get("domain", ""),
        "cloudflare_zone_id": config.get("cloudflare_zone_id", ""),
        "tunnel_id": config.get("cloudflare_tunnel_id", ""),
        "is_default": True,
        "source": "system_config",
    }

    domain_id = (app_doc or {}).get("domain_id")
    if domain_id:
        from bson import ObjectId
        from bson.errors import InvalidId

        try:
            doc = await db.domains.find_one({"_id": ObjectId(domain_id)})
        except InvalidId:
            doc = None
        if doc:
            doc["source"] = "app"
            return doc
        # La app apunta a un dominio borrado. Caer al default es preferible a
        # desplegar contra un FQDN inexistente, pero tiene que quedar en el log.
        logger.warning(
            "App %s references missing domain %s; falling back to default",
            (app_doc or {}).get("name"), domain_id,
        )

    default = await db.domains.find_one({"is_default": True})
    if default:
        default["source"] = "default"
        return default
    return fallback


async def verify(fqdn: str, *, tunnel_id: str = "") -> Dict[str, Any]:
    """Valida que un dominio pueda servir apps publicas. No modifica nada.

    Reporta cada condicion por separado para que el alta en la consola diga
    exactamente que falta, en vez de un error opaco.
    """
    config = await get_system_config()
    token = config.get("cloudflare_token", "")
    account_id = config.get("cloudflare_account_id", "")
    checks: List[Dict[str, str]] = []

    if not token or not account_id:
        checks.append(_check(
            "credentials", "Credenciales de Cloudflare", "fail",
            "No hay token o account_id en la configuracion del sistema.",
        ))
        return {"fqdn": fqdn, "ok": False, "zone_id": None, "checks": checks}

    checks.append(_check(
        "credentials", "Credenciales de Cloudflare", "ok",
        "Cuenta " + account_id[:8] + "...",
    ))

    zone_id = None
    zone_status = None
    async with httpx.AsyncClient(timeout=20) as client:
        try:
            resp = await client.get(f"{CF_API}/zones?name={fqdn}", headers=_headers(token))
            zones = resp.json().get("result", []) if resp.status_code == 200 else []
        except Exception as exc:  # red, DNS, timeout
            checks.append(_check(
                "zone", "Zona en Cloudflare", "fail",
                f"No se pudo consultar la API de Cloudflare: {exc}",
            ))
            return {"fqdn": fqdn, "ok": False, "zone_id": None, "checks": checks}

        if not zones:
            checks.append(_check(
                "zone", "Zona en Cloudflare", "fail",
                f"El token no ve ninguna zona llamada {fqdn}. Agrega el dominio a "
                "esta cuenta de Cloudflare, o revisa que el token tenga permiso "
                "Zone:Read sobre ella.",
            ))
            return {"fqdn": fqdn, "ok": False, "zone_id": None, "checks": checks}

        zone = zones[0]
        zone_id = zone["id"]
        zone_status = zone.get("status")
        zone_account = (zone.get("account") or {}).get("id")

        if zone_status == "active":
            checks.append(_check(
                "zone", "Zona en Cloudflare", "ok", f"Zone {zone_id[:8]}... activa",
            ))
        else:
            nameservers = ", ".join(zone.get("name_servers") or []) or "los que indica Cloudflare"
            checks.append(_check(
                "zone", "Zona en Cloudflare", "fail",
                f"La zona existe pero esta en estado '{zone_status}'. Apunta los "
                f"nameservers del registrador a: {nameservers}.",
            ))

        if zone_account and account_id and zone_account != account_id:
            checks.append(_check(
                "account", "Cuenta propietaria", "fail",
                "La zona pertenece a una cuenta de Cloudflare distinta a la del "
                "tunel; el tunel no podra servir este dominio.",
            ))
        else:
            checks.append(_check(
                "account", "Cuenta propietaria", "ok",
                "La zona vive en la misma cuenta que el tunel.",
            ))

        effective_tunnel = tunnel_id or config.get("cloudflare_tunnel_id", "")
        if not effective_tunnel:
            checks.append(_check(
                "tunnel", "Tunel de Cloudflare", "fail",
                "No hay tunel configurado en esta instalacion; sin el no existe "
                "ruta de entrada para trafico publico.",
            ))
        else:
            try:
                t_resp = await client.get(
                    f"{CF_API}/accounts/{account_id}/cfd_tunnel/{effective_tunnel}",
                    headers=_headers(token),
                )
                deleted = (t_resp.json().get("result") or {}).get("deleted_at") if t_resp.status_code == 200 else True
                if t_resp.status_code == 200 and not deleted:
                    checks.append(_check(
                        "tunnel", "Tunel de Cloudflare", "ok",
                        f"Tunel {effective_tunnel[:8]}... disponible",
                    ))
                else:
                    checks.append(_check(
                        "tunnel", "Tunel de Cloudflare", "fail",
                        "El tunel configurado no existe o fue borrado.",
                    ))
            except Exception as exc:
                checks.append(_check(
                    "tunnel", "Tunel de Cloudflare", "warn",
                    f"No se pudo verificar el tunel: {exc}",
                ))

    ok = all(c["status"] != "fail" for c in checks)
    return {
        "fqdn": fqdn,
        "ok": ok,
        "zone_id": zone_id,
        "zone_status": zone_status,
        "checks": checks,
    }


async def provision(fqdn: str, *, zone_id: str, tunnel_id: str) -> Dict[str, Any]:
    """Cablea un dominio ya validado: reglas de tunel + DNS wildcard y raiz.

    Idempotente. Las reglas del tunel se leen, se **extienden** y se reescriben:
    un PUT ciego borraria el dominio que ya sirve la instalacion.
    """
    config = await get_system_config()
    token = config.get("cloudflare_token", "")
    account_id = config.get("cloudflare_account_id", "")
    if not token or not account_id:
        raise DomainError("Cloudflare no esta configurado en esta instalacion.")
    if not tunnel_id:
        raise DomainError("No hay tunel de Cloudflare al cual asociar el dominio.")

    created: List[str] = []
    async with httpx.AsyncClient(timeout=30) as client:
        cfg_url = f"{CF_API}/accounts/{account_id}/cfd_tunnel/{tunnel_id}/configurations"
        cur_resp = await client.get(cfg_url, headers=_headers(token))
        if cur_resp.status_code != 200:
            raise DomainError(
                f"No se pudo leer la configuracion del tunel (HTTP {cur_resp.status_code})."
            )
        tunnel_cfg = (cur_resp.json().get("result") or {}).get("config") or {}
        ingress = list(tunnel_cfg.get("ingress") or [])

        existing_hosts = {rule.get("hostname") for rule in ingress if rule.get("hostname")}
        new_rules = [
            {"hostname": f"*.{fqdn}", "service": TRAEFIK_SERVICE},
            {"hostname": fqdn, "service": TRAEFIK_SERVICE},
        ]
        additions = [r for r in new_rules if r["hostname"] not in existing_hosts]

        if additions:
            # El catch-all (regla sin hostname) tiene que quedar al final o
            # Cloudflare rechaza la configuracion completa.
            catch_all = [r for r in ingress if not r.get("hostname")]
            routed = [r for r in ingress if r.get("hostname")]
            tunnel_cfg["ingress"] = routed + additions + (catch_all or [{"service": "http_status:404"}])
            put_resp = await client.put(cfg_url, headers=_headers(token), json={"config": tunnel_cfg})
            if put_resp.status_code != 200:
                raise DomainError(
                    f"No se pudieron agregar las reglas del tunel "
                    f"(HTTP {put_resp.status_code}): {put_resp.text[:200]}"
                )
            created.extend(r["hostname"] for r in additions)

        target = f"{tunnel_id}.cfargotunnel.com"
        for name in [f"*.{fqdn}", fqdn]:
            record = {"type": "CNAME", "name": name, "content": target, "proxied": True}
            ex_resp = await client.get(
                f"{CF_API}/zones/{zone_id}/dns_records?type=CNAME&name={name}",
                headers=_headers(token),
            )
            existing = ex_resp.json().get("result", []) if ex_resp.status_code == 200 else []
            if existing:
                await client.put(
                    f"{CF_API}/zones/{zone_id}/dns_records/{existing[0]['id']}",
                    headers=_headers(token), json=record,
                )
            else:
                cr = await client.post(
                    f"{CF_API}/zones/{zone_id}/dns_records",
                    headers=_headers(token), json=record,
                )
                if cr.status_code != 200:
                    raise DomainError(f"No se pudo crear el DNS {name}: {cr.text[:200]}")
            created.append(name)

    logger.info("Domain %s provisioned on tunnel %s", fqdn, tunnel_id)
    return {"fqdn": fqdn, "zone_id": zone_id, "tunnel_id": tunnel_id, "provisioned": created}


async def deprovision(fqdn: str, *, zone_id: str, tunnel_id: str) -> Dict[str, Any]:
    """Quita reglas de tunel y DNS wildcard/raiz de un dominio que se elimina."""
    config = await get_system_config()
    token = config.get("cloudflare_token", "")
    account_id = config.get("cloudflare_account_id", "")
    removed: List[str] = []
    if not token or not account_id or not tunnel_id:
        return {"fqdn": fqdn, "removed": removed, "skipped": "cloudflare-not-configured"}

    hosts = [f"*.{fqdn}", fqdn]
    async with httpx.AsyncClient(timeout=30) as client:
        cfg_url = f"{CF_API}/accounts/{account_id}/cfd_tunnel/{tunnel_id}/configurations"
        cur_resp = await client.get(cfg_url, headers=_headers(token))
        if cur_resp.status_code == 200:
            tunnel_cfg = (cur_resp.json().get("result") or {}).get("config") or {}
            ingress = list(tunnel_cfg.get("ingress") or [])
            kept = [r for r in ingress if r.get("hostname") not in hosts]
            if len(kept) != len(ingress):
                tunnel_cfg["ingress"] = kept
                await client.put(cfg_url, headers=_headers(token), json={"config": tunnel_cfg})
                removed.append("tunnel-rules")

        if zone_id:
            for name in hosts:
                ex_resp = await client.get(
                    f"{CF_API}/zones/{zone_id}/dns_records?type=CNAME&name={name}",
                    headers=_headers(token),
                )
                records = ex_resp.json().get("result", []) if ex_resp.status_code == 200 else []
                for rec in records:
                    await client.delete(
                        f"{CF_API}/zones/{zone_id}/dns_records/{rec['id']}",
                        headers=_headers(token),
                    )
                    removed.append(name)

    return {"fqdn": fqdn, "removed": removed}


async def count_apps_using(domain_id: str, *, is_default: bool) -> int:
    """Apps que quedarian huerfanas si el dominio desaparece.

    El dominio default tambien carga con las apps que nunca fijaron domain_id:
    borrarlo sin contarlas dejaria esas apps apuntando a la nada.
    """
    db = get_db()
    if is_default:
        query = {"$or": [
            {"domain_id": domain_id},
            {"domain_id": None},
            {"domain_id": {"$exists": False}},
        ]}
    else:
        query = {"domain_id": domain_id}
    return await db.apps.count_documents(query)
