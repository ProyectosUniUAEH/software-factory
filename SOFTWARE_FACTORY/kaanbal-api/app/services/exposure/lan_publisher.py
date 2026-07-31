"""LanPublisherService — NodePort / LAN exposure (stub → impl Fase 1/2)."""
from __future__ import annotations

from typing import Optional

from .types import PublisherResult


class LanPublisherService:
    async def publish(
        self,
        *,
        app_name: str,
        env: str,
        node_port: Optional[int] = None,
        lan_ip: str = "",
        ensure: bool = True,
    ) -> PublisherResult:
        if not ensure:
            return PublisherResult(
                name="lan", ok=True, status="skipped", detail="LAN not requested"
            )
        if not lan_ip:
            return PublisherResult(
                name="lan", ok=True, status="pending",
                detail="cluster_lan_ip not configured yet — NodePort will be applied in Fase 2",
            )
        url = f"http://{lan_ip}:{node_port}" if node_port else f"http://{lan_ip}"
        return PublisherResult(
            name="lan", ok=True, status="ok",
            detail=f"LAN URL for {app_name}/{env}",
            urls=[url],
            meta={"lan_ip": lan_ip, "node_port": node_port},
        )
