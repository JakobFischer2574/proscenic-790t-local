import base64
import struct

from robotbona.map_decoder import (
    PIXEL_FLOOR,
    PIXEL_RESERVED,
    PIXEL_UNKNOWN,
    PIXEL_WALL,
    decode_map,
    decode_track,
    render_map_png,
)


def encoded_map(payload: bytes) -> str:
    return base64.b64encode(b"\x00" * 9 + payload).decode("ascii")


def test_map_byte_decodes_four_pixels_high_bits_first():
    # 01 wall, 10 floor, 00 unknown, 11 reserved
    decoded = decode_map(encoded_map(bytes([0b01100011])))
    assert decoded.cells[:4] == (
        PIXEL_WALL,
        PIXEL_FLOOR,
        PIXEL_UNKNOWN,
        PIXEL_RESERVED,
    )
    assert len(decoded.cells) == 10000


def test_map_rle_repeats_following_packed_byte():
    # C2 = repeat the following packed byte twice -> eight logical pixels.
    decoded = decode_map(encoded_map(bytes([0xC2, 0b01010101])))
    assert decoded.cells[:8] == (PIXEL_WALL,) * 8


def test_track_skips_header_and_decodes_signed_xy_pairs():
    raw = b"HEAD" + struct.pack("<bbbb", 1, -2, 3, 4)
    encoded = base64.b64encode(raw).decode("ascii")
    assert decode_track(encoded) == ((1, -2), (3, 4))


def test_rendered_map_is_valid_sized_png():
    png = render_map_png(encoded_map(bytes([0b10101010])), scale=2)
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    assert png[12:16] == b"IHDR"
    width, height = struct.unpack(">II", png[16:24])
    assert (width, height) == (200, 200)
