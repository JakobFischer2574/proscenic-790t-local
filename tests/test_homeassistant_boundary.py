import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
INTEGRATION = ROOT / "custom_components" / "proscenic_790t_local"


def test_manifest_is_modern_local_polling_config_flow():
    manifest = json.loads((INTEGRATION / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["domain"] == "proscenic_790t_local"
    assert manifest["config_flow"] is True
    assert manifest["iot_class"] == "local_polling"
    assert manifest["integration_type"] == "device"
    assert manifest["version"] == "0.1.0"


def test_custom_component_contains_no_robotbona_wire_protocol_implementation():
    forbidden = (
        "transitCmd",
        "LOGIN_ACK_MAGIC",
        "CONTROL_MAGIC",
        "fa 00 c8 00",
        "20008",
        "noteCmd",
    )
    sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in INTEGRATION.glob("*.py")
    )
    for marker in forbidden:
        assert marker not in sources


def test_custom_component_python_files_compile():
    for path in INTEGRATION.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        compile(source, str(path), "exec")


def test_custom_component_translations_are_valid_json():
    for language in ("en", "de"):
        data = json.loads(
            (INTEGRATION / "translations" / f"{language}.json").read_text(encoding="utf-8")
        )
        assert data["title"] == "Proscenic 790T"
