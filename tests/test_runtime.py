import json

import pytest

from robotbona.runtime import DEFAULT_LOCAL_TOKEN, RuntimeConfig


def test_runtime_config_reads_home_assistant_options_file(monkeypatch, tmp_path):
    options = tmp_path / "options.json"
    options.write_text(
        json.dumps(
            {
                "app_key": "SANITIZED_APP",
                "device_id": "SANITIZED_DEVICE",
                "local_token": DEFAULT_LOCAL_TOKEN,
                "persist_interval": 7,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("ROBOTBONA_OPTIONS_FILE", str(options))
    for name in (
        "ROBOTBONA_APP_KEY",
        "ROBOTBONA_DEVICE_ID",
        "ROBOTBONA_LOCAL_TOKEN",
        "ROBOTBONA_PERSIST_INTERVAL",
    ):
        monkeypatch.delenv(name, raising=False)

    config = RuntimeConfig.from_environment()
    assert config.app_key == "SANITIZED_APP"
    assert config.device_id == "SANITIZED_DEVICE"
    assert config.persist_interval == 7


def test_environment_overrides_app_options(monkeypatch, tmp_path):
    options = tmp_path / "options.json"
    options.write_text(
        json.dumps({"app_key": "FROM_FILE", "device_id": "FROM_FILE"}),
        encoding="utf-8",
    )
    monkeypatch.setenv("ROBOTBONA_OPTIONS_FILE", str(options))
    monkeypatch.setenv("ROBOTBONA_APP_KEY", "FROM_ENV")
    monkeypatch.setenv("ROBOTBONA_DEVICE_ID", "DEVICE_ENV")
    config = RuntimeConfig.from_environment()
    assert config.app_key == "FROM_ENV"
    assert config.device_id == "DEVICE_ENV"


def test_runtime_config_requires_installation_identifiers(monkeypatch, tmp_path):
    monkeypatch.setenv("ROBOTBONA_OPTIONS_FILE", str(tmp_path / "missing.json"))
    monkeypatch.delenv("ROBOTBONA_APP_KEY", raising=False)
    monkeypatch.delenv("ROBOTBONA_DEVICE_ID", raising=False)
    with pytest.raises(ValueError, match="app_key is required"):
        RuntimeConfig.from_environment()


def test_runtime_config_rejects_non_32_character_token():
    config = RuntimeConfig(
        app_key="SANITIZED_APP", device_id="SANITIZED_DEVICE", local_token="short"
    )
    with pytest.raises(ValueError, match="32 characters"):
        config.validate()
