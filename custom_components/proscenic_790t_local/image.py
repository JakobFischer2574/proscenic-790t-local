"""Map image entity for Proscenic 790T."""

from __future__ import annotations

from typing import override

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import ProscenicApiError
from .coordinator import ProscenicCoordinator
from .entity import ProscenicEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([ProscenicMapImage(hass, entry.runtime_data, entry)])


class ProscenicMapImage(ProscenicEntity, ImageEntity):
    _attr_translation_key = "map"
    _attr_content_type = "image/png"

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: ProscenicCoordinator,
        entry: ConfigEntry,
    ) -> None:
        ProscenicEntity.__init__(self, coordinator, entry, "map")
        ImageEntity.__init__(self, hass)
        self._last_revision: str | None = None

    @override
    async def async_added_to_hass(self) -> None:
        self._last_revision = self.coordinator.data.get("map_revision")
        if self._last_revision:
            self._attr_image_last_updated = dt_util.utcnow()
        await super().async_added_to_hass()

    @override
    def _handle_coordinator_update(self) -> None:
        revision = self.coordinator.data.get("map_revision")
        if revision != self._last_revision:
            self._last_revision = revision
            if revision:
                self._attr_image_last_updated = dt_util.utcnow()
        super()._handle_coordinator_update()

    @override
    async def async_image(self) -> bytes | None:
        try:
            return await self.coordinator.client.async_map_png()
        except ProscenicApiError:
            return None
