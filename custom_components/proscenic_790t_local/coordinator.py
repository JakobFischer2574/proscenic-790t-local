"""Coordinator for the local Proscenic 790T server API."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ProscenicApiClient, ProscenicApiError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class ProscenicCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: ProscenicApiClient,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
            always_update=False,
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.client.async_status()
        except ProscenicApiError as exc:
            raise UpdateFailed(f"local API update failed: {exc}") from exc

    async def async_run_command(self, path: str) -> None:
        try:
            await self.client.async_command(path)
        except ProscenicApiError as exc:
            raise UpdateFailed(f"local API command failed: {exc}") from exc
        await self.async_request_refresh()
