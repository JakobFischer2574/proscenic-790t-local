"""Shared entity base for the Proscenic 790T integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import ProscenicCoordinator


class ProscenicEntity(CoordinatorEntity[ProscenicCoordinator]):
    _attr_has_entity_name = True

    def __init__(
        self, coordinator: ProscenicCoordinator, entry: ConfigEntry, key: str
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name="Proscenic 790T",
        )

    @property
    def robot_connected(self) -> bool:
        return bool(self.coordinator.data.get("connected"))
