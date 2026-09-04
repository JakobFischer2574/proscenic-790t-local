"""Capability metadata with explicit evidence levels.

This module deliberately separates protocol-accepted values from behaviour that
was physically confirmed on the tested firmware.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Evidence = Literal["confirmed", "observed", "historical", "unknown"]


@dataclass(frozen=True, slots=True)
class CapabilityValue:
    value: str
    name: str
    evidence: Evidence


@dataclass(frozen=True, slots=True)
class RobotCapabilities:
    commands: dict[str, CapabilityValue]
    cleaning_modes: dict[str, CapabilityValue]
    fan_values: dict[str, CapabilityValue]

    def confirmed_cleaning_modes(self) -> dict[str, CapabilityValue]:
        return {k: v for k, v in self.cleaning_modes.items() if v.evidence == "confirmed"}

    def confirmed_fan_values(self) -> dict[str, CapabilityValue]:
        return {k: v for k, v in self.fan_values.items() if v.evidence == "confirmed"}

    def as_dict(self) -> dict[str, object]:
        def dump(items: dict[str, CapabilityValue]) -> dict[str, dict[str, str]]:
            return {
                key: {"value": item.value, "name": item.name, "evidence": item.evidence}
                for key, item in items.items()
            }
        return {
            "commands": dump(self.commands),
            "cleaning_modes": dump(self.cleaning_modes),
            "fan_values": dump(self.fan_values),
        }


DEFAULT_CAPABILITIES = RobotCapabilities(
    commands={
        "start": CapabilityValue("100", "start", "confirmed"),
        "stop": CapabilityValue("102", "stop", "confirmed"),
        "home": CapabilityValue("104", "return_to_dock", "confirmed"),
        "mode": CapabilityValue("106", "cleaning_mode", "confirmed"),
        "fan": CapabilityValue("110", "fan", "confirmed"),
        "voice_on": CapabilityValue("123", "voice_on", "confirmed"),
        "voice_off": CapabilityValue("125", "voice_off", "confirmed"),
        "map": CapabilityValue("131", "map_status_request", "confirmed"),
        "set_time": CapabilityValue("139", "set_time", "observed"),
    },
    cleaning_modes={
        "3": CapabilityValue("3", "normal", "confirmed"),
        "4": CapabilityValue("4", "edge", "confirmed"),
        "6": CapabilityValue("6", "area", "confirmed"),
        "1": CapabilityValue("1", "spiral", "observed"),
        "8": CapabilityValue("8", "deep", "observed"),
        "10": CapabilityValue("10", "scrub", "observed"),
        "11": CapabilityValue("11", "auto", "observed"),
    },
    fan_values={
        "1": CapabilityValue("1", "off", "observed"),
        "2": CapabilityValue("2", "normal", "confirmed"),
        "3": CapabilityValue("3", "turbo", "confirmed"),
        "4": CapabilityValue("4", "eco", "observed"),
    },
)
