"""Sensors for the Proscenic 790T local API."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ProscenicCoordinator
from .entity import ProscenicEntity


@dataclass(frozen=True, slots=True)
class SensorSpec:
    key: str
    translation_key: str
    getter: Callable[[dict[str, Any]], Any]
    device_class: SensorDeviceClass | None = None
    unit: str | None = None
    category: EntityCategory | None = None
    enabled: bool = True


def _state(key: str):
    return lambda data: (data.get("state") or {}).get(key)


SENSORS = (
    SensorSpec("battery", "battery", _state("battery"), SensorDeviceClass.BATTERY, PERCENTAGE),
    SensorSpec(
        "status",
        "status",
        lambda data: (data.get("friendly") or {}).get("work_state"),
    ),
    SensorSpec("work_state_raw", "work_state_raw", _state("workState"), category=EntityCategory.DIAGNOSTIC),
    SensorSpec("work_mode_raw", "work_mode_raw", _state("workMode"), category=EntityCategory.DIAGNOSTIC),
    SensorSpec("error_raw", "error_raw", _state("error"), category=EntityCategory.DIAGNOSTIC),
    SensorSpec("fan_raw", "fan_raw", _state("fan"), category=EntityCategory.DIAGNOSTIC, enabled=False),
    SensorSpec("clear_area_raw", "clear_area_raw", _state("clearArea"), category=EntityCategory.DIAGNOSTIC, enabled=False),
    SensorSpec("clear_time_raw", "clear_time_raw", _state("clearTime"), category=EntityCategory.DIAGNOSTIC, enabled=False),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(ProscenicSensor(coordinator, entry, spec) for spec in SENSORS)


class ProscenicSensor(ProscenicEntity, SensorEntity):
    def __init__(
        self, coordinator: ProscenicCoordinator, entry: ConfigEntry, spec: SensorSpec
    ) -> None:
        super().__init__(coordinator, entry, spec.key)
        self.spec = spec
        self._attr_translation_key = spec.translation_key
        self._attr_device_class = spec.device_class
        self._attr_native_unit_of_measurement = spec.unit
        self._attr_entity_category = spec.category
        self._attr_entity_registry_enabled_default = spec.enabled

    @property
    def native_value(self):
        value = self.spec.getter(self.coordinator.data)
        if self.spec.device_class == SensorDeviceClass.BATTERY:
            try:
                return int(value) if value is not None else None
            except (TypeError, ValueError):
                return None
        return value
