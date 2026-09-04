"""Thin HTTP client for the proscenic-790t-local server API."""

from __future__ import annotations

from typing import Any

from aiohttp import ClientError, ClientResponseError, ClientSession, ClientTimeout


class ProscenicApiError(Exception):
    """Raised when the local server API cannot satisfy a request."""


class ProscenicApiClient:
    def __init__(self, session: ClientSession, host: str, port: int) -> None:
        self.session = session
        self.host = host
        self.port = port
        formatted_host = f"[{host}]" if ":" in host and not host.startswith("[") else host
        self.base_url = f"http://{formatted_host}:{port}"
        self.timeout = ClientTimeout(total=10)

    async def async_status(self) -> dict[str, Any]:
        payload = await self._json("GET", "/api/status")
        status = payload.get("status")
        if not isinstance(status, dict):
            raise ProscenicApiError("local API returned no status object")
        return status

    async def async_command(self, path: str) -> dict[str, Any]:
        return await self._json("POST", path)

    async def async_map_png(self) -> bytes | None:
        try:
            async with self.session.get(
                f"{self.base_url}/api/map.png", timeout=self.timeout
            ) as response:
                if response.status == 404:
                    return None
                response.raise_for_status()
                if not response.headers.get("Content-Type", "").startswith("image/png"):
                    raise ProscenicApiError("map endpoint did not return a PNG image")
                return await response.read()
        except (ClientError, TimeoutError) as exc:
            raise ProscenicApiError(str(exc)) from exc

    async def _json(self, method: str, path: str) -> dict[str, Any]:
        try:
            async with self.session.request(
                method, f"{self.base_url}{path}", timeout=self.timeout
            ) as response:
                payload = await response.json(content_type=None)
                if not isinstance(payload, dict):
                    raise ProscenicApiError("local API returned a non-object JSON response")
                if response.status >= 400 or payload.get("ok") is not True:
                    message = payload.get("error") or f"HTTP {response.status}"
                    raise ProscenicApiError(str(message))
                return payload
        except ProscenicApiError:
            raise
        except (ClientError, ClientResponseError, TimeoutError, ValueError) as exc:
            raise ProscenicApiError(str(exc)) from exc
