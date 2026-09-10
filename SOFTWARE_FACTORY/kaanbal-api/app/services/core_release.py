"""
Core Release Service — procedencia y actualizaciones del core (ADR-002)
======================================================================
Responde tres preguntas que hoy una celula no puede responder:

  1. Que version soy.                    -> read_provenance()
  2. Hay algo mas nuevo publicado.       -> check_updates()
  3. Estoy modificada localmente.        -> detect_drift()

Una celula sin procedencia no puede compararse con upstream ni saber a que
volver si un upgrade sale mal, asi que todo lo demas cuelga de esto.

La release es un artefacto inmutable publicado como GitHub Release en el
monorepo, fijada por digest y no por tag: un tag puede moverse, un digest no.
Eso es lo que hace que dos celulas en la misma version corran el mismo binario
y que el rollback sea exacto.

Solo lectura. Aplicar un upgrade es otra cosa y vive en su propio modulo.
"""

import logging
from typing import Any, Dict, List, Optional

import httpx

from app.db import get_db

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"

# Repo publico que publica las releases del engine.
UPSTREAM_OWNER = "ProyectosUniUAEH"
UPSTREAM_REPO = "software-factory"

# Los tres componentes que forman el engine. Coincide con
# installer/corebuild.py: CORE_COMPONENTS.
CORE_COMPONENTS = ("kaanbal-api", "kaanbal-console", "kaanbal-agent")

CHANNEL_STABLE = "stable"
CHANNEL_DEV = "dev"
CHANNEL_CUSTOM = "custom"


def _gh_headers(token: str = "") -> Dict[str, str]:
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


async def _config() -> Dict[str, Any]:
    db = get_db()
    return await db.system_config.find_one({"_id": "main"}) or {}


async def read_provenance() -> Dict[str, Any]:
    """Que version corre esta celula.

    Una instalacion anterior a ADR-002 no tiene procedencia. En vez de inventar
    una, se reporta `unknown`: decir "v1.0.0" sin saberlo haria que la celula
    creyera estar al dia y nunca se actualizara.
    """
    config = await _config()
    release = config.get("core_release") or {}
    if not release:
        return {
            "known": False,
            "channel": CHANNEL_STABLE,
            "version": "unknown",
            "upstream_sha": None,
            "components": {},
            "reason": (
                "Esta celula se instalo antes de que se registrara la "
                "procedencia del core. Aplica una release para fijarla."
            ),
        }
    return {
        "known": True,
        "channel": release.get("channel") or CHANNEL_STABLE,
        "version": release.get("version") or "unknown",
        "upstream_sha": release.get("upstream_sha"),
        "components": release.get("components") or {},
        "applied_at": release.get("applied_at"),
        "applied_by": release.get("applied_by"),
    }


async def list_releases(limit: int = 20) -> List[Dict[str, Any]]:
    """Releases publicadas upstream, de la mas nueva a la mas vieja."""
    config = await _config()
    token = config.get("github_token") or config.get("git_token") or ""
    url = f"{GITHUB_API}/repos/{UPSTREAM_OWNER}/{UPSTREAM_REPO}/releases?per_page={limit}"
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(url, headers=_gh_headers(token))
            if resp.status_code != 200:
                logger.warning("GitHub releases HTTP %s: %s", resp.status_code, resp.text[:200])
                return []
            payload = resp.json()
    except Exception as exc:
        logger.warning("No se pudieron consultar releases upstream: %s", exc)
        return []

    releases = []
    for item in payload:
        if item.get("draft"):
            continue
        releases.append({
            "version": item.get("tag_name"),
            "name": item.get("name"),
            "notes": item.get("body") or "",
            "prerelease": bool(item.get("prerelease")),
            "published_at": item.get("published_at"),
            "url": item.get("html_url"),
        })
    return releases


async def detect_drift() -> Dict[str, Any]:
    """Componentes modificados localmente respecto a la release aplicada.

    Tunear el core es legitimo, asi que la deriva es un estado que se reporta,
    no un error. Lo que no es aceptable es pisarla en silencio durante un
    upgrade: por eso se detecta antes de ofrecer uno.
    """
    config = await _config()
    provenance = await read_provenance()
    recorded = provenance.get("components") or {}
    org = (config.get("github_org") or config.get("bitbucket_workspace") or "").strip()
    token = config.get("github_token") or config.get("git_token") or ""

    if not org or not token:
        return {"detectable": False, "reason": "Sin org o token de GitHub configurados", "components": {}}
    if not provenance["known"]:
        return {
            "detectable": False,
            "reason": "Sin procedencia registrada: no hay contra que comparar",
            "components": {},
        }

    components: Dict[str, Any] = {}
    async with httpx.AsyncClient(timeout=20) as client:
        for name in CORE_COMPONENTS:
            expected = (recorded.get(name) or {}).get("repo_sha")
            url = f"{GITHUB_API}/repos/{org}/{name}/commits/main"
            try:
                resp = await client.get(url, headers=_gh_headers(token))
                head = resp.json().get("sha") if resp.status_code == 200 else None
            except Exception as exc:
                logger.warning("drift check %s: %s", name, exc)
                head = None

            if not head or not expected:
                components[name] = {"custom": False, "head_sha": head, "expected_sha": expected,
                                    "unknown": True}
                continue
            components[name] = {
                "custom": head != expected,
                "head_sha": head,
                "expected_sha": expected,
                "unknown": False,
            }

    any_custom = any(c.get("custom") for c in components.values())
    return {"detectable": True, "any_custom": any_custom, "components": components}


async def check_updates() -> Dict[str, Any]:
    """Resumen que consume la consola: version actual, disponible y deriva.

    No aplica nada. El disparo del upgrade es manual y con changelog a la vista
    (ADR-002): un cambio malo aplicado solo llegaria a todos los clientes sin
    que nadie lo intercepte.
    """
    provenance = await read_provenance()
    releases = await list_releases()
    drift = await detect_drift()

    channel = provenance.get("channel") or CHANNEL_STABLE
    candidates = [r for r in releases if channel == CHANNEL_DEV or not r["prerelease"]]
    latest = candidates[0] if candidates else None

    current_version = provenance.get("version")
    update_available = bool(
        latest and current_version and latest["version"] and latest["version"] != current_version
    )
    # Una celula sin procedencia no puede afirmar que esta al dia; ofrecerle la
    # ultima release es la forma de fijarla.
    if latest and not provenance["known"]:
        update_available = True

    pending = []
    if latest and current_version:
        for release in candidates:
            if release["version"] == current_version:
                break
            pending.append(release)

    return {
        "current": provenance,
        "latest": latest,
        "update_available": update_available,
        "pending_releases": pending,
        "drift": drift,
        "blocked_by_drift": bool(drift.get("any_custom")) and update_available,
        "channel": channel,
    }


async def write_provenance(
    *,
    version: str,
    upstream_sha: Optional[str],
    components: Dict[str, Any],
    channel: str = CHANNEL_STABLE,
    applied_by: str = "installer",
) -> Dict[str, Any]:
    """Fija la procedencia de la celula. La escribe el instalador y cada upgrade."""
    from datetime import datetime

    db = get_db()
    release = {
        "version": version,
        "upstream_sha": upstream_sha,
        "components": components,
        "channel": channel,
        "applied_at": datetime.utcnow(),
        "applied_by": applied_by,
    }
    await db.system_config.update_one(
        {"_id": "main"}, {"$set": {"core_release": release}}, upsert=True,
    )
    logger.info("Core provenance set: %s (%s)", version, channel)
    return release
