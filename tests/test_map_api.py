import base64

from robotbona.api_server import dispatch_api
from robotbona.service import RobotService
from robotbona.state import RobotState


class FakeConnection:
    def __init__(self, state):
        self.state = state

    def send_control(self, transit_cmd, *, extra_value=None):
        return 1


def make_service():
    state = RobotState(connected=True)
    return RobotService(state, FakeConnection(state))


def test_status_exposes_revision_not_map_blob():
    service = make_service()
    service.state.map_data = base64.b64encode(b"\x00" * 9 + b"\xaa").decode()
    status = service.status()
    assert status["map_revision"] is not None
    assert service.state.map_data not in repr(status)


def test_map_png_endpoint_is_binary_and_returns_404_before_first_map():
    service = make_service()
    missing = dispatch_api(service, "GET", "/api/map.png")
    assert missing.status == 404
    assert missing.content_type.startswith("application/json")

    service.state.map_data = base64.b64encode(b"\x00" * 9 + b"\xaa").decode()
    response = dispatch_api(service, "GET", "/api/map.png")
    assert response.status == 200
    assert response.content_type == "image/png"
    assert isinstance(response.body, bytes)
    assert response.body.startswith(b"\x89PNG")
