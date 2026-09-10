"""
Core Router — version y actualizaciones del engine (ADR-002)
============================================================
Endpoints de solo lectura sobre la procedencia del core. Aplicar un upgrade
es una transaccion aparte y la conduce un Job de Kubernetes, no este proceso:
si `kaanbal-api` promoviera su propia imagen, el proceso que conduce el upgrade
seria el que muere a mitad de camino.
"""

import logging

from fastapi import APIRouter, Depends

from app.routers.auth import get_current_active_user
from app.services import core_release

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(get_current_active_user)])


@router.get("/version")
async def get_core_version():
    """Que version corre esta celula."""
    return await core_release.read_provenance()


@router.get("/updates")
async def get_core_updates():
    """Hay algo mas nuevo publicado, y esta celula esta modificada."""
    return await core_release.check_updates()


@router.get("/releases")
async def get_core_releases(limit: int = 20):
    """Releases publicadas upstream, con notas."""
    return {"releases": await core_release.list_releases(limit=limit)}


@router.get("/drift")
async def get_core_drift():
    """Componentes del core modificados localmente."""
    return await core_release.detect_drift()
