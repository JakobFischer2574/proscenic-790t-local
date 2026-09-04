# Architecture

## Design principle

The project is split into a robot-facing protocol/service layer and client adapters.

```text
Proscenic 790T
      |
      | RobotBona-compatible protocol
      v
+------------------------------+
| Core / local RobotBona server|
|------------------------------|
| HTTP token endpoint          |
| TCP session management       |
| login / ACK / keepalive      |
| command construction         |
| raw + interpreted state      |
| capabilities                 |
| map / track decoding         |
+---------------+--------------+
                |
                | stable local API
                v
+------------------------------+
| Clients                      |
|------------------------------|
| Home Assistant integration   |
| optional web UI              |
| scripts / other automation   |
+------------------------------+
```

The Home Assistant integration is not allowed to become the authoritative source of robot protocol knowledge.

## Core responsibilities

The core/server should own:

- RobotBona HTTP compatibility.
- Persistent TCP connection handling.
- Packet framing/parsing.
- Login and dynamic learning of connection-specific data such as auth code and robot IP.
- Command IDs and parameterized command serialization.
- Raw robot state.
- Conservative friendly state interpretation.
- Robot capabilities and their evidence/confidence level.
- Map and track decoding.
- Persistence needed for continuity, e.g. last completed map.
- A stable local API for clients.

The core API should expose raw values alongside interpretations wherever proprietary semantics remain uncertain.

## Proposed internal module boundaries

```text
src/robotbona/
    protocol.py       frame encoding/decoding, magic values
    http_server.py    robot-facing token/log HTTP compatibility
    tcp_server.py     robot connection lifecycle
    commands.py       command definitions and ordered payload building
    state.py          raw state model + conservative interpretation
    capabilities.py   tested-supported features and confidence levels
    map_decoder.py    map/track decode
    service.py        orchestration

src/robotbona_api/
    app.py            local client API
```

The exact framework for the local API can be chosen later. Keep the robot-facing protocol code independent of any web framework.

## Home Assistant layer

The Home Assistant custom integration should consume the local API and expose entities such as:

- vacuum entity: start, pause/stop, return to dock
- battery sensor
- connection/status sensors
- cleaning mode selector
- fan selector
- voice switch
- map/camera/image entity
- optional diagnostics exposing raw protocol values

Home Assistant scheduling should use normal HA automations. Native robot scheduling is not required for the initial integration.

## Deployment options

### Home Assistant App

Preferred when running Home Assistant OS/Supervisor-style deployments.

The app runs the local RobotBona server in its own process/container, separate from Home Assistant Core. The custom integration talks to the app API.

Advantages:

- lifecycle managed from Home Assistant
- protocol server isolated from HA Core
- HA integration can reload without reimplementing the robot TCP protocol

The robot-facing HTTP port should avoid conflicting with Home Assistant's own HTTP listener. A configurable high port such as `18080` is suitable, with TCP `20008` retained for RobotBona traffic unless deployment constraints require another configured value.

### Proxmox LXC / container

A dedicated LXC/container is also a first-class deployment target and may be the most robust option.

Advantages:

- robot remains connected even while Home Assistant restarts/updates
- simple dedicated IP/ports
- server usable by clients other than Home Assistant

The core/server must therefore not assume that it runs inside Home Assistant.

## Development strategy

1. Keep a sanitized copy of the known-working monolithic v4 implementation under `reference/`.
2. Add byte-level regression tests for known packet construction.
3. Extract protocol and state code incrementally into `src/`.
4. Add a local API without changing robot-facing wire behaviour.
5. Package the server for the selected deployment target.
6. Add the thin Home Assistant custom integration.
7. Add map presentation and user-facing refinements after protocol/state stability.

Avoid a big-bang rewrite of the working protocol implementation.
