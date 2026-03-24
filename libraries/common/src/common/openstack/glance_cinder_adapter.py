from __future__ import annotations

from typing import Any

import httpx


class GlanceCinderAdapter:
    def __init__(self, glance_url: str, cinder_url: str, timeout_seconds: float = 5.0):
        self.glance_url = glance_url.rstrip("/")
        self.cinder_url = cinder_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def list_images(self, token: str) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.get(f"{self.glance_url}/v2/images", headers={"X-Auth-Token": token})
            resp.raise_for_status()
            return resp.json().get("images", [])

    async def list_volumes(self, token: str) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.get(f"{self.cinder_url}/volumes/detail", headers={"X-Auth-Token": token})
            resp.raise_for_status()
            return resp.json().get("volumes", [])
