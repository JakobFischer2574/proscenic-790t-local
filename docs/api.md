# Local API

The local API is deliberately separated from the RobotBona wire protocol. It is intended for Home Assistant and any other LAN client. It does not expose auth codes, device IDs, tokens or packet-level protocol details.

Default deployment ports are chosen by the deployment layer; the API itself does not assume a specific port.

## Read endpoints

- `GET /api/health` — process/robot connection health.
- `GET /api/status` — public robot state, conservative friendly state, raw status values and capability metadata.
- `GET /api/map` — latest base64 map/track payload and cleaning statistics. Decoding/rendering can be layered on top without changing the control API.

## Control endpoints

- `POST /api/start`
- `POST /api/stop`
- `POST /api/home`
- `POST /api/map` — ask the robot for map/status (`transitCmd=131`).
- `POST /api/voice/on`
- `POST /api/voice/off`
- `POST /api/mode/{value}` — accepts only modes marked `confirmed` by the core capability model.
- `POST /api/fan/{value}` — accepts values known by the capability model and returns their evidence level.

Successful controls return the RobotBona command sequence number. A `409` means the command could not be sent because no active/logged-in robot connection exists. Invalid/unsupported values return `400`.

## State philosophy

The API returns both raw proprietary values and conservative friendly labels. Unknown values are preserved rather than reinterpreted. The Home Assistant integration must consume this API instead of duplicating RobotBona command IDs, packet framing or state semantics.
