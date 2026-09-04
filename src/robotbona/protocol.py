"""RobotBona wire framing extracted from the empirically working v4 baseline.

Do not reinterpret unknown fields here.  These byte layouts are wire-level
behaviour confirmed against the tested Proscenic 790T firmware.
"""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from datetime import datetime
from typing import Mapping, Any

HEADER_SIZE = 20
MAX_PACKET_SIZE = 1024 * 1024

LOGIN_ACK_MAGIC = b"\x11\x00\xc8\x00"
NORMAL_ACK_MAGIC = b"\x19\x00\xc8\x00"
KEEPALIVE_ACK_MAGIC = b"\x11\x01\xc8\x00"
CONTROL_MAGIC = b"\xfa\x00\xc8\x00"
CONTROL_RESPONSE_MAGIC = b"\xfa\x00\x00\x00"

DEFAULT_MIDDLE = b"\x01\x00\x00\x00"
DEFAULT_FLAG = b"\x00\x00\x00\x00"
CONTROL_MIDDLE = b"\x00\x00\x09\x01"
NORMAL_ACK_FLAG = b"\x01\x00\x00\x00"
KEEPALIVE_FLAG = b"\xe7\x03\x00\x00"


@dataclass(frozen=True, slots=True)
class PacketHeader:
    total_length: int
    magic: bytes
    middle: bytes
    sequence: int
    flag: bytes


def json_payload(obj: Mapping[str, Any]) -> bytes:
    """Serialize exactly like the working reference: compact ASCII JSON + LF."""
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=True).encode("ascii") + b"\n"


def build_packet(
    magic4: bytes,
    payload: bytes,
    sequence: int,
    *,
    middle4: bytes = DEFAULT_MIDDLE,
    flag4: bytes = DEFAULT_FLAG,
) -> bytes:
    for name, value in (("magic4", magic4), ("middle4", middle4), ("flag4", flag4)):
        if len(value) != 4:
            raise ValueError(f"{name} must be exactly 4 bytes")
    if not 0 <= sequence <= 0xFFFFFFFF:
        raise ValueError("sequence must fit in uint32")

    total_length = HEADER_SIZE + len(payload)
    return (
        struct.pack("<I", total_length)
        + magic4
        + middle4
        + struct.pack("<I", sequence)
        + flag4
        + payload
    )


def parse_header(header: bytes) -> PacketHeader:
    if len(header) != HEADER_SIZE:
        raise ValueError(f"expected {HEADER_SIZE} header bytes, got {len(header)}")
    total_length = struct.unpack("<I", header[0:4])[0]
    if total_length < HEADER_SIZE or total_length > MAX_PACKET_SIZE:
        raise ValueError(f"invalid packet length {total_length}")
    return PacketHeader(
        total_length=total_length,
        magic=header[4:8],
        middle=header[8:12],
        sequence=struct.unpack("<I", header[12:16])[0],
        flag=header[16:20],
    )


def build_login_ack(sequence: int, *, now: datetime | None = None) -> bytes:
    timestamp = (now or datetime.now()).strftime("%Y-%m-%d-%H-%M-%S")
    payload = json_payload(
        {"msg": "login succeed", "result": 0, "version": "1.0", "time": timestamp}
    )
    return build_packet(LOGIN_ACK_MAGIC, payload, sequence)


def build_normal_ack(sequence: int) -> bytes:
    return build_packet(
        NORMAL_ACK_MAGIC,
        json_payload({"msg": "OK", "result": 0, "version": "1.0"}),
        sequence,
        middle4=DEFAULT_MIDDLE,
        flag4=NORMAL_ACK_FLAG,
    )


def build_keepalive_ack(sequence: int) -> bytes:
    return build_packet(
        KEEPALIVE_ACK_MAGIC,
        b"",
        sequence,
        middle4=DEFAULT_MIDDLE,
        flag4=KEEPALIVE_FLAG,
    )
