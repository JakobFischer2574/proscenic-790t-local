import json

from robotbona.persistence import StatePersistence
from robotbona.state import RobotState


def test_persistence_keeps_public_state_and_map_without_credentials(tmp_path):
    state = RobotState(connected=True)
    state.update_from_message(
        {
            "value": {
                "token": "SECRET_TOKEN",
                "deviceId": "SECRET_DEVICE",
                "authCode": "SECRET_AUTH",
                "deviceIp": "192.0.2.63",
            }
        }
    )
    state.update_from_message(
        {"value": {"noteCmd": "102", "battery": "88", "workState": "5"}}
    )
    state.map_data = "SANITIZED_MAP"
    state.track_data = "SANITIZED_TRACK"

    store = StatePersistence(tmp_path)
    store.save(state)

    raw_file = store.state_path.read_text(encoding="utf-8")
    assert "SECRET_TOKEN" not in raw_file
    assert "SECRET_DEVICE" not in raw_file
    assert "SECRET_AUTH" not in raw_file
    payload = json.loads(raw_file)
    assert payload["state"]["battery"] == "88"
    assert store.map_path.read_text(encoding="ascii") == "SANITIZED_MAP"
    assert store.track_path.read_text(encoding="ascii") == "SANITIZED_TRACK"


def test_persistence_restore_never_restores_live_connection_or_credentials(tmp_path):
    store = StatePersistence(tmp_path)
    store.state_path.write_text(
        json.dumps({"state": {"battery": "73", "workState": "2"}}),
        encoding="utf-8",
    )
    store.map_path.write_text("MAP", encoding="ascii")

    state = RobotState(connected=True)
    store.load_into(state)
    assert state.connected is False
    assert state.values["battery"] == "73"
    assert state.map_data == "MAP"
    assert state.session.auth_code is None
