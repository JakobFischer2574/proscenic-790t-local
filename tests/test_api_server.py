from robotbona.api_server import dispatch_api
from robotbona.service import RobotService
from robotbona.state import RobotState


class FakeConnection:
    def __init__(self, state, *, fail=False):
        self.state = state
        self.calls = []
        self.fail = fail

    def send_control(self, transit_cmd, *, extra_value=None):
        if self.fail:
            raise RuntimeError("no active robot connection")
        self.calls.append((str(transit_cmd), extra_value))
        return 1234


def make_service(*, fail=False):
    state = RobotState(connected=not fail)
    connection = FakeConnection(state, fail=fail)
    return RobotService(state, connection), connection


def test_status_and_health_are_transport_independent():
    service, _ = make_service()
    response = dispatch_api(service, "GET", "/api/status")
    assert response.status == 200
    assert response.body["ok"] is True
    assert response.body["status"]["connected"] is True

    health = dispatch_api(service, "GET", "/api/health")
    assert health.body == {"ok": True, "connected": True}


def test_control_routes_map_to_core_commands():
    service, connection = make_service()
    assert dispatch_api(service, "POST", "/api/start").body["sequence"] == 1234
    assert dispatch_api(service, "POST", "/api/home").body["sequence"] == 1234
    assert connection.calls == [("100", None), ("104", None)]


def test_mode_endpoint_rejects_unconfirmed_mode():
    service, connection = make_service()
    accepted = dispatch_api(service, "POST", "/api/mode/6")
    assert accepted.status == 200
    assert connection.calls[-1] == ("106", {"mode": "6"})

    rejected = dispatch_api(service, "POST", "/api/mode/11")
    assert rejected.status == 400
    assert "not confirmed" in rejected.body["error"]


def test_fan_endpoint_returns_capability_evidence():
    service, connection = make_service()
    response = dispatch_api(service, "POST", "/api/fan/3")
    assert response.status == 200
    assert response.body["evidence"] == "confirmed"
    assert connection.calls[-1] == ("110", {"fan": "3"})


def test_disconnected_control_returns_conflict_not_server_error():
    service, _ = make_service(fail=True)
    response = dispatch_api(service, "POST", "/api/start")
    assert response.status == 409
    assert response.body["ok"] is False


def test_map_endpoint_exposes_only_latest_decoded_inputs_not_credentials():
    service, _ = make_service()
    service.state.map_data = "SANITIZED_BASE64_MAP"
    service.state.track_data = "SANITIZED_BASE64_TRACK"
    response = dispatch_api(service, "GET", "/api/map")
    assert response.body["map"]["map"] == "SANITIZED_BASE64_MAP"
    assert response.body["map"]["track"] == "SANITIZED_BASE64_TRACK"


def test_unknown_endpoint_is_404():
    service, _ = make_service()
    response = dispatch_api(service, "GET", "/api/nope")
    assert response.status == 404
