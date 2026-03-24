from __future__ import annotations

from typing import Any

import httpx


class NovaAdapter:
    def __init__(self, base_url: str, timeout_seconds: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def list_servers(self, token: str) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.get(
                f"{self.base_url}/servers/detail",
                headers={"X-Auth-Token": token},
            )
            resp.raise_for_status()
            return resp.json().get("servers", [])
