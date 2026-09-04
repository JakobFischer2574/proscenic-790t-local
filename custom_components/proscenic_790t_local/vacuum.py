"""Vacuum entity for Proscenic 790T."""

from __future__ import annotations

from typing import Any, override

from homeassistant.components.vacuum import (
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)
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
    async_add_entities([ProscenicVacuum(entry.runtime_data, entry)])


class ProscenicVacuum(ProscenicEntity, StateVacuumEntity):
    _attr_name = None
    _attr_supported_features = (
        VacuumEntityFeature.START
        | VacuumEntityFeature.STOP
        | VacuumEntityFeature.PAUSE
        | VacuumEntityFeature.RETURN_HOME
        | VacuumEntityFeature.STATE
    )

    def __init__(self, coordinator: ProscenicCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "vacuum")

    @property
    @override
    def available(self) -> bool:
        return self.coordinator.last_update_success and self.robot_connected

    @property
    @override
    def activity(self) -> VacuumActivity | None:
        state = self.coordinator.data.get("state") or {}
        error = str(state.get("error", "0"))
        if error not in ("", "0", "None"):
            return VacuumActivity.ERROR
        friendly = (self.coordinator.data.get("friendly") or {}).get("work_state")
        return {
            "cleaning": VacuumActivity.CLEANING,
            "returning_or_docking": VacuumActivity.RETURNING,
            "docked_or_charging": VacuumActivity.DOCKED,
            "docked_full_or_charging": VacuumActivity.DOCKED,
            "pending_or_transitional": VacuumActivity.IDLE,
        }.get(friendly)

    @override
    async def async_start(self) -> None:
        await self.coordinator.async_run_command("/api/start")

    @override
    async def async_stop(self, **kwargs: Any) -> None:
        await self.coordinator.async_run_command("/api/stop")

    @override
    async def async_pause(self) -> None:
        await self.coordinator.async_run_command("/api/stop")

    @override
    async def async_return_to_base(self, **kwargs: Any) -> None:
        await self.coordinator.async_run_command("/api/home")
