import json

from robotbona.commands import (
    CommandBuilder,
    CommandSequencer,
    ControlContext,
    build_control_packet,
)
from robotbona.protocol import CONTROL_MAGIC, CONTROL_MIDDLE, parse_header

CONTEXT = ControlContext(
    auth_code="SANITIZED_AUTH",
    device_ip="192.0.2.63",
    device_port="8888",
)


def payload_object(packet: bytes):
    return json.loads(packet[20:].decode("ascii"))


def test_control_header_matches_working_v4_reference():
    packet = build_control_packet(CONTEXT, "100", 0x2701)
    header = parse_header(packet[:20])
    assert header.magic == CONTROL_MAGIC
    assert header.middle == CONTROL_MIDDLE
    assert header.sequence == 0x2701
    assert header.flag == b"\x00\x00\x00\x00"


def test_control_envelope_matches_working_reference():
    obj = payload_object(build_control_packet(CONTEXT, "104", 0x2702))
    assert obj["cmd"] == 0
    assert obj["control"] == {
        "authCode": "SANITIZED_AUTH",
        "deviceIp": "192.0.2.63",
        "devicePort": "8888",
        "targetId": "0",
        "targetType": "3",
    }
    assert obj["seq"] == 0
    assert obj["value"] == {"transitCmd": "104"}


def test_extra_value_is_serialized_before_transit_cmd():
    packet = build_control_packet(
        CONTEXT, "106", 0x2703, extra_value={"mode": "4"}
    )
    raw = packet[20:].decode("ascii")
    assert '"value":{"mode":"4","transitCmd":"106"}' in raw
    assert raw.index('"mode"') < raw.index('"transitCmd"')


def test_fan_value_order_is_preserved_too():
    packet = build_control_packet(
        CONTEXT, "110", 0x2704, extra_value={"fan": "3"}
    )
    assert b'"value":{"fan":"3","transitCmd":"110"}' in packet


def test_sequence_numbers_advance_once_per_built_command():
    builder = CommandBuilder(CommandSequencer(start=0x2701))
    first, first_packet = builder.build(CONTEXT, "100")
    second, second_packet = builder.build(CONTEXT, "102")
    assert (first, second) == (0x2701, 0x2702)
    assert parse_header(first_packet[:20]).sequence == first
    assert parse_header(second_packet[:20]).sequence == second
