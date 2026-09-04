"""Server-to-robot command construction.

The order of keys in ``value`` is intentionally preserved.  On the tested
firmware, mode/fan parameters must appear before ``transitCmd``.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Mapping, Any

from .protocol import CONTROL_MAGIC, CONTROL_MIDDLE, build_packet, json_payload


@dataclass(frozen=True, slots=True)
class ControlContext:
    auth_code: str
    device_ip: str
    device_port: str = "8888"
    target_id: str = "0"
    target_type: str = "3"


class CommandSequencer:
    def __init__(self, start: int = 0x2701) -> None:
        self._next = start
        self._lock = threading.Lock()

    def next(self) -> int:
        with self._lock:
            value = self._next
            self._next = (self._next + 1) & 0xFFFFFFFF
            return value


def build_control_packet(
    context: ControlContext,
    transit_cmd: str | int,
    sequence: int,
    *,
    extra_value: Mapping[str, Any] | None = None,
) -> bytes:
    if not context.auth_code:
        raise ValueError("auth_code is required")
    if not context.device_ip:
        raise ValueError("device_ip is required")

    value_obj: dict[str, str] = {}
    if extra_value:
        for key, value in extra_value.items():
            value_obj[str(key)] = str(value)
    value_obj["transitCmd"] = str(transit_cmd)

    body_obj = {
        "cmd": 0,
        "control": {
            "authCode": str(context.auth_code),
            "deviceIp": str(context.device_ip),
            "devicePort": str(context.device_port or "8888"),
            "targetId": str(context.target_id),
            "targetType": str(context.target_type),
        },
        "seq": 0,
        "value": value_obj,
    }
    return build_packet(
        CONTROL_MAGIC,
        json_payload(body_obj),
        sequence,
        middle4=CONTROL_MIDDLE,
        flag4=b"\x00\x00\x00\x00",
    )


class CommandBuilder:
    def __init__(self, sequencer: CommandSequencer | None = None) -> None:
        self.sequencer = sequencer or CommandSequencer()

    def build(
        self,
        context: ControlContext,
        transit_cmd: str | int,
        *,
        extra_value: Mapping[str, Any] | None = None,
    ) -> tuple[int, bytes]:
        sequence = self.sequencer.next()
        return sequence, build_control_packet(
            context, transit_cmd, sequence, extra_value=extra_value
        )
