"""Decode and render RobotBona map/track payloads.

The wire-level decoding algorithm is based on the RobotBona mapping research in
felix-engelmann/robotbona (MIT licensed; see THIRD_PARTY_NOTICES.md) and is kept
in the core so Home Assistant and other clients never need proprietary map
knowledge.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
import struct
import zlib

MAP_WIDTH = 100
MAP_HEIGHT = 100
MAP_HEADER_BYTES = 9
TRACK_HEADER_BYTES = 4

PIXEL_UNKNOWN = 0
PIXEL_WALL = 1
PIXEL_FLOOR = 2
PIXEL_RESERVED = 3


@dataclass(frozen=True, slots=True)
class DecodedMap:
    width: int
    height: int
    cells: tuple[int, ...]

    def cell(self, x: int, y: int) -> int:
        return self.cells[y * self.width + x]


def _b64decode(value: str, kind: str) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"invalid {kind} base64 payload") from exc


def _unpack_map_byte(value: int) -> tuple[int, int, int, int]:
    # RobotBona stores the first logical pixel in the high two bits.
    return (
        (value >> 6) & 0b11,
        (value >> 4) & 0b11,
        (value >> 2) & 0b11,
        value & 0b11,
    )


def decode_map(value: str) -> DecodedMap:
    raw = _b64decode(value, "map")
    if len(raw) < MAP_HEADER_BYTES:
        raise ValueError("map payload is shorter than the 9-byte header")

    encoded = raw[MAP_HEADER_BYTES:]
    cells: list[int] = []
    index = 0
    expected = MAP_WIDTH * MAP_HEIGHT

    while index < len(encoded) and len(cells) < expected:
        current = encoded[index]
        if current & 0b11000000 == 0b11000000:
            count = current & 0b00111111
            index += 1
            if index >= len(encoded):
                raise ValueError("truncated map RLE marker")

            # Captured RobotBona payloads can extend the count with a second
            # 6-bit marker before the byte to repeat.
            if encoded[index] & 0b11000000 == 0b11000000:
                count = (count << 6) | (encoded[index] & 0b00111111)
                index += 1
                if index >= len(encoded):
                    raise ValueError("truncated extended map RLE marker")

            packed = encoded[index]
            pixels = _unpack_map_byte(packed)
            for _ in range(count):
                cells.extend(pixels)
                if len(cells) >= expected:
                    break
        else:
            cells.extend(_unpack_map_byte(current))
        index += 1

    if len(cells) < expected:
        cells.extend([PIXEL_UNKNOWN] * (expected - len(cells)))
    elif len(cells) > expected:
        del cells[expected:]

    return DecodedMap(MAP_WIDTH, MAP_HEIGHT, tuple(cells))


def decode_track(value: str | None) -> tuple[tuple[int, int], ...]:
    if not value:
        return ()
    raw = _b64decode(value, "track")
    if len(raw) < TRACK_HEADER_BYTES:
        raise ValueError("track payload is shorter than the 4-byte header")
    coordinate_bytes = raw[TRACK_HEADER_BYTES:]
    if len(coordinate_bytes) % 2:
        raise ValueError("track payload contains an incomplete coordinate pair")
    if not coordinate_bytes:
        return ()
    coordinates = struct.unpack(f"<{len(coordinate_bytes)}b", coordinate_bytes)
    return tuple(zip(coordinates[0::2], coordinates[1::2], strict=True))


def render_map_png(
    map_value: str,
    track_value: str | None = None,
    *,
    scale: int = 4,
) -> bytes:
    """Render the decoded 100x100 map and track to a dependency-free PNG."""
    if scale < 1 or scale > 16:
        raise ValueError("map scale must be between 1 and 16")

    decoded = decode_map(map_value)
    track = decode_track(track_value)
    width = decoded.width * scale
    height = decoded.height * scale

    palette = {
        PIXEL_UNKNOWN: (232, 232, 232),
        PIXEL_WALL: (35, 35, 35),
        PIXEL_FLOOR: (255, 255, 255),
        PIXEL_RESERVED: (150, 150, 150),
    }
    track_color = (35, 120, 55)

    rows: list[bytearray] = []
    for y in range(decoded.height):
        logical = bytearray()
        for x in range(decoded.width):
            color = palette[decoded.cell(x, y)]
            logical.extend(bytes(color) * scale)
        for _ in range(scale):
            rows.append(bytearray(logical))

    def paint(px: int, py: int) -> None:
        if not (0 <= px < decoded.width and 0 <= py < decoded.height):
            return
        for sy in range(py * scale, min((py + 1) * scale, height)):
            start = px * scale * 3
            end = start + scale * 3
            rows[sy][start:end] = bytes(track_color) * scale

    if track:
        previous = track[0]
        paint(*previous)
        for point in track[1:]:
            for pixel in _line_points(previous[0], previous[1], point[0], point[1]):
                paint(*pixel)
            previous = point

    scanlines = b"".join(b"\x00" + bytes(row) for row in rows)
    return _png(width, height, scanlines)


def _line_points(x0: int, y0: int, x1: int, y1: int):
    """Yield integer points along a line using Bresenham's algorithm."""
    dx = abs(x1 - x0)
    sx = 1 if x0 < x1 else -1
    dy = -abs(y1 - y0)
    sy = 1 if y0 < y1 else -1
    error = dx + dy
    while True:
        yield x0, y0
        if x0 == x1 and y0 == y1:
            return
        doubled = 2 * error
        if doubled >= dy:
            error += dy
            x0 += sx
        if doubled <= dx:
            error += dx
            y0 += sy


def _png(width: int, height: int, scanlines: bytes) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return signature + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(scanlines, 9)) + chunk(b"IEND", b"")
