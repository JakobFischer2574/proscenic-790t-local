import pytest

from robotbona.service import RobotService
from robotbona.state import RobotState


class FakeConnection:
    def __init__(self, state):
        self.state = state
        self.calls = []
        self.sequence = 100

    def send_control(self, transit_cmd, *, extra_value=None):
        self.sequence += 1
        self.calls.append((str(transit_cmd), extra_value))
        return self.sequence


def make_service():
    state = RobotState(connected=True)
    connection = FakeConnection(state)
    return RobotService(state, connection), connection


def test_named_commands_delegate_to_core_connection():
    service, connection = make_service()
    seq = service.command("start")
    assert seq == 101
    assert connection.calls == [("100", None)]


def test_only_physically_confirmed_cleaning_modes_are_allowed():
    service, connection = make_service()
    service.set_mode("4")
    assert connection.calls[-1] == ("106", {"mode": "4"})
    with pytest.raises(ValueError, match="not confirmed"):
        service.set_mode("11")


def test_fan_validation_uses_capability_metadata_and_returns_evidence():
    service, connection = make_service()
    _seq, evidence = service.set_fan("3")
    assert evidence == "confirmed"
    assert connection.calls[-1] == ("110", {"fan": "3"})

    _seq, evidence = service.set_fan("4")
    assert evidence == "observed"
    with pytest.raises(ValueError, match="unsupported"):
        service.set_fan("99")


def test_status_does_not_publish_session_credentials():
    service, _connection = make_service()
    service.state.update_from_message(
        {"value": {"token": "SECRET", "deviceId": "DEVICE", "authCode": "AUTH", "deviceIp": "192.0.2.63"}}
    )
    status = service.status()
    serialized = repr(status)
    assert "SECRET" not in serialized
    assert "AUTH" not in serialized
    assert "DEVICE" not in serialized
    assert status["confirmed_cleaning_modes"] == ["3", "4", "6"]
