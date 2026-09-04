"""Voice control switch for Proscenic 790T."""

from homeassistant.components.switch import SwitchEntity
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
    async_add_entities([ProscenicVoiceSwitch(entry.runtime_data, entry)])


class ProscenicVoiceSwitch(ProscenicEntity, SwitchEntity):
    """Optimistic switch because the tested firmware does not report voice state."""

    _attr_translation_key = "voice"
    _attr_assumed_state = True

    def __init__(self, coordinator: ProscenicCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "voice")
        self._is_on: bool | None = None

    @property
    def is_on(self) -> bool | None:
        return self._is_on

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self.robot_connected

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_run_command("/api/voice/on")
        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_run_command("/api/voice/off")
        self._is_on = False
        self.async_write_ha_state()
