"""Robot session and state model.

Raw RobotBona values are always retained internally. Friendly labels are
conservative and must not erase uncertainty in proprietary state semantics.
Client-facing snapshots redact credentials and large map/track blobs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

STATUS_KEYS = ("workState", "workMode", "battery", "fan", "error", "direction", "brush")
CLEANING_KEYS = ("clearArea", "clearTime", "clearSign", "clearModule")
PUBLIC_RAW_EXCLUDE = frozenset({"token", "authCode", "deviceId", "appKey", "map", "track"})


@dataclass(slots=True)
class RobotSessionInfo:
    device_id: str | None = None
    auth_code: str | None = None
    device_ip: str | None = None
    device_port: str = "8888"

    def control_ready(self) -> bool:
        return bool(self.auth_code and self.device_ip)

    def public_dict(self) -> dict[str, Any]:
        # Auth code and device ID are deliberately excluded from client-facing state.
        return {"device_ip": self.device_ip, "device_port": self.device_port}


@dataclass(slots=True)
class RobotState:
    connected: bool = False
    session: RobotSessionInfo = field(default_factory=RobotSessionInfo)
    values: dict[str, Any] = field(default_factory=dict)
    raw_value: dict[str, Any] = field(default_factory=dict)
    map_data: str | None = None
    track_data: str | None = None

    def update_from_message(self, obj: Mapping[str, Any]) -> None:
        value = obj.get("value")
        if not isinstance(value, Mapping):
            return

        # Keep the complete value internally for diagnostics and future protocol work.
        self.raw_value.update(dict(value))

        if "token" in value:
            self.session.device_id = _optional_str(value.get("deviceId"))
            self.session.auth_code = _optional_str(value.get("authCode"))
            self.session.device_ip = _optional_str(value.get("deviceIp"))
            self.session.device_port = _optional_str(value.get("devicePort")) or "8888"

        note = _optional_str(value.get("noteCmd"))
        if note == "102":
            for key in STATUS_KEYS:
                self.values[key] = value.get(key)
        elif note == "101":
            for key in CLEANING_KEYS:
                self.values[key] = value.get(key)
            if isinstance(value.get("map"), str):
                self.map_data = value["map"]
            if isinstance(value.get("track"), str):
                self.track_data = value["track"]

    @property
    def work_state_label(self) -> str:
        raw = _optional_str(self.values.get("workState"))
        return {
            "1": "cleaning",
            "2": "pending_or_transitional",
            "4": "returning_or_docking",
            "5": "docked_or_charging",
            "6": "docked_full_or_charging",
        }.get(raw, f"unknown_{raw}" if raw is not None else "unknown")

    def public_raw(self) -> dict[str, Any]:
        """Return diagnostics-safe raw values without credentials or map blobs."""
        return {
            key: value
            for key, value in self.raw_value.items()
            if key not in PUBLIC_RAW_EXCLUDE
        }

    def public_snapshot(self) -> dict[str, Any]:
        return {
            "connected": self.connected,
            "robot": self.session.public_dict(),
            "state": dict(self.values),
            "friendly": {"work_state": self.work_state_label},
            "raw": self.public_raw(),
            "map_available": self.map_data is not None,
            "track_available": self.track_data is not None,
        }


def _optional_str(value: Any) -> str | None:
    return None if value is None else str(value)
