from robotbona.state import RobotState


def test_login_learns_internal_control_context_without_exposing_secrets():
    state = RobotState()
    state.update_from_message(
        {
            "value": {
                "token": "SANITIZED_TOKEN",
                "deviceId": "SANITIZED_DEVICE",
                "authCode": "SANITIZED_AUTH",
                "deviceIp": "192.0.2.63",
                "devicePort": "8888",
            }
        }
    )
    assert state.session.control_ready()
    public = state.public_snapshot()
    assert "auth_code" not in public["robot"]
    assert "device_id" not in public["robot"]


def test_status_preserves_raw_unknown_values():
    state = RobotState()
    state.update_from_message(
        {
            "value": {
                "noteCmd": "102",
                "workState": "7",
                "workMode": "99",
                "battery": "42",
                "mysteryField": "kept",
            }
        }
    )
    assert state.values["workState"] == "7"
    assert state.work_state_label == "unknown_7"
    assert state.raw_value["mysteryField"] == "kept"


def test_empirically_supported_work_state_labels_are_conservative():
    state = RobotState()
    for raw, expected in {
        "1": "cleaning",
        "2": "pending_or_transitional",
        "4": "returning_or_docking",
        "5": "docked_or_charging",
        "6": "docked_full_or_charging",
    }.items():
        state.update_from_message({"value": {"noteCmd": "102", "workState": raw}})
        assert state.work_state_label == expected
