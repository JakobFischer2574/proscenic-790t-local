# proscenic-790t-local

Fully local, cloudless control for the **Proscenic 790T** vacuum robot by emulating the RobotBona services it expects on the local network.

> **Status:** early reverse-engineering / development project. The empirically proven protocol baseline is kept separate from the Home Assistant layer.

## Goals

- Run the robot without a live RobotBona/Proscenic cloud connection.
- Keep protocol knowledge and robot state in a reusable core/server, **not inside the Home Assistant integration**.
- Expose a stable local API for Home Assistant and other clients.
- Preserve empirically confirmed wire behaviour with regression tests.
- Decode and expose map/track data locally.

## Architecture

```text
Proscenic 790T
    |
    | RobotBona-compatible HTTP + TCP
    v
Local RobotBona server / core
    |- token endpoint
    |- TCP session, login, ACK, keepalive
    |- commands
    |- robot state and capabilities
    |- map / track decoding and PNG rendering
    `- local API
          |
          +--> Home Assistant integration (thin client)
          `--> other local clients
```

The Home Assistant integration is a presentation/control adapter. It is not the authoritative implementation of the proprietary robot protocol and is not the only place where robot capabilities and state semantics are defined.

## Empirically confirmed on the tested 790T

Tested firmware:

- Wi-Fi module: `1.0.41`
- MCU: `1.8.2614(828)`

Confirmed control commands:

| Command | Meaning | Status |
|---:|---|---|
| `100` | Start cleaning | confirmed |
| `102` | Stop / pause | confirmed |
| `104` | Return to dock | confirmed |
| `106` | Cleaning mode | confirmed |
| `110` | Fan setting | confirmed |
| `123` | Voice on | confirmed |
| `125` | Voice off | confirmed |
| `131` | Map/status request | confirmed |
| `139` | Set clock | observed, **not confirmed working** |

Confirmed cleaning modes on the tested unit:

| Value | Behaviour | Status |
|---:|---|---|
| `3` | normal/default/random cleaning | confirmed |
| `4` | edge cleaning | confirmed |
| `6` | area cleaning | confirmed |
| `1`, `8`, `10`, `11` | accepted by protocol, but no distinct mode observed on this firmware | not exposed as confirmed modes |

For commands with extra values, JSON field order matters on the tested firmware. Preserve the extra parameter before `transitCmd`, for example:

```json
{"mode":"4","transitCmd":"106"}
```

not:

```json
{"transitCmd":"106","mode":"4"}
```

See [`docs/confirmed-behavior.md`](docs/confirmed-behavior.md) and [`docs/protocol.md`](docs/protocol.md) for details and confidence levels.

## Repository layout

```text
reference/          sanitized working monolithic baseline
src/robotbona/      reusable RobotBona core/server and local API
custom_components/  Home Assistant custom integration (thin API client)
ha-app/             Home Assistant App packaging
docs/               protocol, API, deployment and integration notes
tests/              regression/boundary tests and sanitized fixtures
```

## Privacy / public-repository policy

Do **not** commit real device identifiers, MAC addresses, auth codes, Wi-Fi credentials, private IP assignments, packet captures, raw proxy logs, or captured cloud/local tokens. Use sanitized fixtures and runtime configuration instead.

## Prior art and attribution

This project is an independent reverse-engineering effort and is not affiliated with Proscenic or RobotBona. Earlier community work, especially [`felix-engelmann/robotbona`](https://github.com/felix-engelmann/robotbona), helped establish parts of the RobotBona protocol and map decoding. See [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

Historical Home Assistant work in [`deblockt/hass-proscenic-790T-vacuum`](https://github.com/deblockt/hass-proscenic-790T-vacuum) was also useful as a behavioural reference. Protocol facts are independently verified where marked as confirmed.

## Disclaimer

Use at your own risk. Reverse-engineered behaviour can vary by firmware and hardware revision. Unknown status and error values must not be guessed or presented as authoritative.
