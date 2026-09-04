"""Capability-driven cleaning-mode and fan selectors."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ProscenicCoordinator
from .entity import ProscenicEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [
            ProscenicCleaningModeSelect(coordinator, entry),
            ProscenicFanSelect(coordinator, entry),
        ]
    )


def _capability_map(data: dict, group: str, *, confirmed_only: bool) -> dict[str, str]:
    capabilities = ((data.get("capabilities") or {}).get(group) or {})
    result: dict[str, str] = {}
    for value, metadata in capabilities.items():
        if not isinstance(metadata, dict):
            continue
        if confirmed_only and metadata.get("evidence") != "confirmed":
            continue
        name = str(metadata.get("name") or value)
        result[name] = str(metadata.get("value") or value)
    return result


class _CapabilitySelect(ProscenicEntity, SelectEntity):
    group = ""
    state_key = ""
    confirmed_only = False

    @property
    def mapping(self) -> dict[str, str]:
        return _capability_map(
            self.coordinator.data, self.group, confirmed_only=self.confirmed_only
        )

    @property
    def options(self) -> list[str]:
        return list(self.mapping)

    @property
    def current_option(self) -> str | None:
        raw = str((self.coordinator.data.get("state") or {}).get(self.state_key, ""))
        for name, value in self.mapping.items():
            if value == raw:
                return name
        return None

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self.robot_connected


class ProscenicCleaningModeSelect(_CapabilitySelect):
    _attr_translation_key = "cleaning_mode"
    group = "cleaning_modes"
    state_key = "workMode"
    confirmed_only = True

    def __init__(self, coordinator: ProscenicCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "cleaning_mode")

    async def async_select_option(self, option: str) -> None:
        value = self.mapping[option]
        await self.coordinator.async_run_command(f"/api/mode/{value}")


class ProscenicFanSelect(_CapabilitySelect):
    _attr_translation_key = "fan"
    group = "fan_values"
    state_key = "fan"

    def __init__(self, coordinator: ProscenicCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "fan")

    async def async_select_option(self, option: str) -> None:
        value = self.mapping[option]
        await self.coordinator.async_run_command(f"/api/fan/{value}")
