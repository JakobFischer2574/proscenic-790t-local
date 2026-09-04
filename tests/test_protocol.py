from datetime import datetime, timezone
import json
import struct

from robotbona.protocol import (
    HEADER_SIZE,
    KEEPALIVE_ACK_MAGIC,
    KEEPALIVE_FLAG,
    LOGIN_ACK_MAGIC,
    NORMAL_ACK_FLAG,
    NORMAL_ACK_MAGIC,
    build_keepalive_ack,
    build_login_ack,
    build_normal_ack,
    build_packet,
    parse_header,
)


def test_packet_has_exact_20_byte_header_and_little_endian_sequence():
    packet = build_packet(b"ABCD", b"xyz", 0x12345678)
    assert len(packet) == 23
    assert struct.unpack("<I", packet[:4])[0] == 23
    assert packet[4:8] == b"ABCD"
    assert packet[8:12] == b"\x01\x00\x00\x00"
    assert packet[12:16] == b"\x78\x56\x34\x12"
    assert packet[16:20] == b"\x00\x00\x00\x00"
    assert packet[HEADER_SIZE:] == b"xyz"


def test_login_ack_matches_reference_shape():
    now = datetime(2026, 9, 4, 13, 1, 11, tzinfo=timezone.utc)
    packet = build_login_ack(32, now=now)
    header = parse_header(packet[:20])
    payload = json.loads(packet[20:].decode("ascii"))
    assert header.magic == LOGIN_ACK_MAGIC
    assert header.sequence == 32
    assert payload == {
        "msg": "login succeed",
        "result": 0,
        "version": "1.0",
        "time": "2026-09-04-13-01-11",
    }


def test_normal_ack_magic_and_flag_match_reference():
    packet = build_normal_ack(77)
    header = parse_header(packet[:20])
    assert header.magic == NORMAL_ACK_MAGIC
    assert header.flag == NORMAL_ACK_FLAG
    assert header.sequence == 77
    assert packet.endswith(b'{"msg":"OK","result":0,"version":"1.0"}\n')


def test_keepalive_ack_is_header_only_with_confirmed_flag():
    packet = build_keepalive_ack(34)
    header = parse_header(packet)
    assert len(packet) == HEADER_SIZE
    assert header.magic == KEEPALIVE_ACK_MAGIC
    assert header.flag == KEEPALIVE_FLAG
    assert header.sequence == 34
