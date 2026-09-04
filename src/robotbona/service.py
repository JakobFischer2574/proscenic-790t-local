"""High-level local service facade over the RobotBona core.

This is the client-facing domain layer. It owns no Home Assistant semantics and
constructs no wire packets itself; commands are delegated to RobotConnection.
"""

from __future__ import annotations

import hashlib
from typing import Any, Protocol

from .capabilities import DEFAULT_CAPABILITIES, RobotCapabilities
from .map_decoder import render_map_png
from .state import RobotState


class ControlConnection(Protocol):
    state: RobotState

    def send_control(
        self,
        transit_cmd: str | int,
        *,
        extra_value: dict[str, object] | None = None,
    ) -> int: ...


class RobotService:
    def __init__(
        self,
        state: RobotState,
        connection: ControlConnection,
        *,
        capabilities: RobotCapabilities = DEFAULT_CAPABILITIES,
    ) -> None:
        self.state = state
        self.connection = connection
        self.capabilities = capabilities

    def status(self) -> dict[str, Any]:
        snapshot = self.state.public_snapshot()
        snapshot["capabilities"] = self.capabilities.as_dict()
        snapshot["confirmed_cleaning_modes"] = list(
            self.capabilities.confirmed_cleaning_modes().keys()
        )
        snapshot["confirmed_fan_values"] = list(
            self.capabilities.confirmed_fan_values().keys()
        )
        snapshot["map_revision"] = self.map_revision()
        return snapshot

    def map_revision(self) -> str | None:
        if self.state.map_data is None:
            return None
        digest = hashlib.sha256()
        digest.update(self.state.map_data.encode("ascii"))
        digest.update(b"\0")
        if self.state.track_data is not None:
            digest.update(self.state.track_data.encode("ascii"))
        return digest.hexdigest()[:16]

    def map_snapshot(self) -> dict[str, Any]:
        return {
            "map": self.state.map_data,
            "track": self.state.track_data,
            "revision": self.map_revision(),
            "clearArea": self.state.values.get("clearArea"),
            "clearTime": self.state.values.get("clearTime"),
            "clearSign": self.state.values.get("clearSign"),
            "clearModule": self.state.values.get("clearModule"),
        }

    def map_png(self) -> bytes:
        if self.state.map_data is None:
            raise LookupError("no map is available yet")
        return render_map_png(self.state.map_data, self.state.track_data)

    def command(self, name: str) -> int:
        capability = self.capabilities.commands.get(name)
        if capability is None:
            raise ValueError(f"unsupported command: {name}")
        return self.connection.send_control(capability.value)

    def set_mode(self, mode: str | int) -> int:
        value = str(mode)
        capability = self.capabilities.cleaning_modes.get(value)
        if capability is None or capability.evidence != "confirmed":
            raise ValueError(f"cleaning mode {value} is not confirmed on this firmware")
        command = self.capabilities.commands["mode"].value
        return self.connection.send_control(command, extra_value={"mode": value})

    def set_fan(self, fan: str | int) -> tuple[int, str]:
        value = str(fan)
        capability = self.capabilities.fan_values.get(value)
        if capability is None:
            raise ValueError(f"unsupported fan value: {value}")
        command = self.capabilities.commands["fan"].value
        sequence = self.connection.send_control(command, extra_value={"fan": value})
        return sequence, capability.evidence
