# proscenic-790t-local

Fully local, cloudless control for the **Proscenic 790T** vacuum robot by emulating the RobotBona services it expects on the local network.

> **Status:** end-to-end hardware tested on a real Proscenic 790T with Wi-Fi firmware `1.0.41` and MCU firmware `1.8.2614(828)`: robot → local RobotBona replacement → local API → Home Assistant integration, including start, stop, return-to-dock, state, battery, cleaning modes, fan control and map/track rendering.
>
> This is still a reverse-engineering project. Behaviour can differ on other firmware revisions.

## What this project does

The original 790T expects two RobotBona services on the network: an HTTP/token service and a persistent TCP service. This project replaces those services locally, keeps the proprietary protocol implementation in a reusable core, exposes a small local JSON API, and provides a Home Assistant integration as a thin client of that API.

```text
Proscenic 790T
    |
    | HTTP :80 + RobotBona TCP :20008
    v
Proscenic 790T Local server/core
    |- token endpoint
    |- TCP login / ACK / keepalive
    |- robot commands
    |- robot state + capability metadata
    |- map / track decoding + PNG rendering
    `- local API :8090
          |
          +--> Home Assistant integration
          `--> other local clients
```

The Home Assistant integration deliberately does **not** duplicate the proprietary RobotBona protocol. The core/server is authoritative; Home Assistant only consumes the stable local API.

## Supported / confirmed on the tested robot

Tested firmware:

- Wi-Fi module: `1.0.41`
- MCU: `1.8.2614(828)`

Confirmed commands:

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
| `1`, `8`, `10`, `11` | accepted by protocol, but no distinct mode observed on this firmware | observed only |

Fan values `2` (normal) and `3` (turbo) are confirmed. Values `1` and `4` have been observed but are not treated as equally well confirmed.

Map and track payloads are decoded locally and exposed as a PNG to Home Assistant.

## Important port quirk: the tested 790T needs HTTP on host port 80

This matters.

The container/server uses internal HTTP port `18080`, but the tested firmware only connected reliably when the robot-facing **host port was 80**. Provisioning with another `jPort` can return success while the robot still never completes the subsequent RobotBona login.

For the tested firmware, use:

```text
robot HTTP     HOME_ASSISTANT_IP:80    -> App/container :18080
robot TCP      HOME_ASSISTANT_IP:20008 -> App/container :20008
local API      HOME_ASSISTANT_IP:8090  -> App/container :8090
```

If port 80 is already occupied on your Home Assistant host, run the server on another LAN IP (for example a small Proxmox/LXC host) or use a dedicated LAN proxy/NAT rule that presents port 80 to the robot and forwards it to the server's internal/listening HTTP port.

## Recommended installation: Home Assistant OS / Supervised

The repository contains both:

1. a **Home Assistant App** that runs the local RobotBona replacement, and
2. a **custom integration** that creates the Home Assistant device/entities.

The current App image supports `amd64`.

### Prerequisites

- Proscenic 790T.
- Home Assistant OS or Supervised on `amd64` for the App installation path below.
- Robot and Home Assistant on mutually reachable LANs; same LAN is simplest.
- Robot Wi-Fi must be usable on 2.4 GHz (ESP8266).
- TCP host ports `80`, `20008` and `8090` available/reachable on the Home Assistant host.
- A computer/phone that can temporarily join the robot's setup Wi-Fi.

Do **not** expose ports `80`, `20008` or `8090` to the public internet. The local API is intended for a trusted LAN and currently has no authentication layer.

### Step 1 — Add this repository to the Home Assistant App store

In Home Assistant:

**Settings → Apps → App store / Install app → ⋮ → Repositories**

Add:

```text
https://github.com/JakobFischer2574/proscenic-790t-local
```

Then install **Proscenic 790T Local**.

### Step 2 — Check the App network mappings

In **Proscenic 790T Local → Network**, use:

```text
container 18080/tcp -> host 80
container 20008/tcp -> host 20008
container 8090/tcp  -> host 8090
```

The first mapping is intentionally asymmetric because of the port-80 firmware quirk described above.

### Step 3 — Put the robot into Wi-Fi/setup mode

Put the 790T into its normal Wi-Fi provisioning / SoftAP mode. The robot should expose a Wi-Fi network similar to:

```text
Proscenic_XXXXXX
```

Connect your computer to that network. The robot is normally reachable at:

```text
192.168.4.1
```

### Step 4 — Provision the robot to your Home Assistant host and read its identifiers

The provisioning response contains the robot's `deviceId` and `appKey`. Treat both as private runtime configuration; do not post them in public issues or commit them to Git.

The following PowerShell flow is the one validated during development:

```powershell
$ssid = [uri]::EscapeDataString("YOUR_WIFI_SSID")
$pwd  = [uri]::EscapeDataString("YOUR_WIFI_PASSWORD")
$ha   = "YOUR_HOME_ASSISTANT_LAN_IP"

$url = "http://192.168.4.1/robot/getRobotInfo.do?ssid=$ssid&pwd=$pwd&jDomain=$ha&jPort=80&sDomain=$ha&sPort=20008&cleanSTime=5"

$response = Invoke-WebRequest -UseBasicParsing -Uri $url -Headers @{ "User-Agent" = "blapp" }
$body = if ($response.Content -is [byte[]]) {
    [Text.Encoding]::UTF8.GetString($response.Content)
} else {
    [string]$response.Content
}

$info = $body | ConvertFrom-Json
$info.result
$info.data.deviceId
$info.data.appKey
```

Expected provisioning result:

```text
0
```

A successful provisioning response means the robot accepted the configuration. It does **not** by itself prove that the subsequent HTTP/TCP login succeeded; verify that in Step 6.

After provisioning, reconnect your computer to the normal LAN if necessary.

### Step 5 — Configure and start the Home Assistant App

Open **Proscenic 790T Local → Configuration** and enter the values obtained above:

```yaml
app_key: "YOUR_APP_KEY"
device_id: "YOUR_DEVICE_ID"
local_token: "LOCAL790T00000000000000000000000"
persist_interval: 5
```

The supplied `local_token` is a generated local dummy token of the required length, not a captured vendor-cloud credential. You can leave it unchanged for the initial setup.

Start the App.

If the robot was provisioned before the App started and does not reconnect after a short wait, power-cycle the robot or repeat the provisioning step.

### Step 6 — Verify the local server before installing the HA integration

From another machine on the LAN:

```powershell
Test-NetConnection YOUR_HOME_ASSISTANT_LAN_IP -Port 80
Test-NetConnection YOUR_HOME_ASSISTANT_LAN_IP -Port 20008
Test-NetConnection YOUR_HOME_ASSISTANT_LAN_IP -Port 8090
```

All three should report:

```text
TcpTestSucceeded : True
```

Then:

```powershell
Invoke-RestMethod http://YOUR_HOME_ASSISTANT_LAN_IP:8090/api/health
```

The target state is:

```text
ok   connected
--   ---------
True True
```

You can inspect the public robot state with:

```powershell
Invoke-RestMethod http://YOUR_HOME_ASSISTANT_LAN_IP:8090/api/status | ConvertTo-Json -Depth 10
```

### Step 7 — Install the custom Home Assistant integration

HACS installation is **not yet provided**. Install the integration manually by copying:

```text
custom_components/proscenic_790t_local
```

from this repository into Home Assistant's custom-components directory.

Canonical Home Assistant path:

```text
/config/custom_components/proscenic_790t_local
```

Some Home Assistant Apps/file-management environments expose the same configuration directory as `/homeassistant`. In the File editor App, for example, you may see:

```text
/homeassistant/custom_components/proscenic_790t_local
```

One convenient File editor workflow, with Git enabled, is:

```sh
rm -rf /tmp/proscenic-790t-local
git clone --depth 1 https://github.com/JakobFischer2574/proscenic-790t-local.git /tmp/proscenic-790t-local
mkdir -p /homeassistant/custom_components
rm -rf /homeassistant/custom_components/proscenic_790t_local
cp -r /tmp/proscenic-790t-local/custom_components/proscenic_790t_local /homeassistant/custom_components/
```

If your shell exposes the Home Assistant configuration root as `/config`, replace `/homeassistant` with `/config` in the commands above.

Restart Home Assistant completely after copying the integration.

### Step 8 — Add the Proscenic integration

Go to:

**Settings → Devices & services → Add integration → Proscenic 790T**

Enter:

```text
Host: YOUR_HOME_ASSISTANT_LAN_IP
Port: 8090
```

Use the Home Assistant host LAN IP, not `127.0.0.1`.

The integration creates one device with entities including:

- vacuum: start, stop/pause, return to dock
- battery sensor
- connectivity binary sensor
- conservative status sensor
- raw diagnostic sensors
- cleaning-mode select (confirmed modes only)
- fan select
- voice on/off switch (assumed state because the tested firmware does not report voice state)
- map image

### Step 9 — Functional test

Test start, stop and return-to-dock from Home Assistant. Then request/update map data and verify the map image.

The same operations can be tested directly against the API:

```powershell
Invoke-RestMethod -Method Post http://YOUR_HOME_ASSISTANT_LAN_IP:8090/api/start
Invoke-RestMethod -Method Post http://YOUR_HOME_ASSISTANT_LAN_IP:8090/api/stop
Invoke-RestMethod -Method Post http://YOUR_HOME_ASSISTANT_LAN_IP:8090/api/home
Invoke-RestMethod -Method Post http://YOUR_HOME_ASSISTANT_LAN_IP:8090/api/map
```

Map PNG:

```text
http://YOUR_HOME_ASSISTANT_LAN_IP:8090/api/map.png
```

## Troubleshooting

### `/api/health` is reachable but `connected` stays `false`

Check all of the following:

- Robot is back on the normal Wi-Fi and reachable.
- Home Assistant host port `80` is actually open.
- Home Assistant host port `20008` is actually open.
- App is running with the correct `app_key` and `device_id`.
- Robot was provisioned with `jPort=80` and `sPort=20008`.
- Robot and Home Assistant can route to each other; guest/client isolation can break this.

The most important tested-firmware gotcha is **HTTP port 80**. Provisioning with `jPort=18080` returned success in testing but the robot did not complete login. Reprovisioning with `jPort=80` immediately produced `connected=true`.

### Integration does not appear in Home Assistant

- Confirm the directory name is exactly `proscenic_790t_local`.
- Confirm `manifest.json` exists directly inside that directory.
- Restart Home Assistant completely; YAML reload is not enough for a newly added custom integration.

### Map is unavailable

First make sure the robot is connected, then request a map refresh:

```powershell
Invoke-RestMethod -Method Post http://YOUR_HOME_ASSISTANT_LAN_IP:8090/api/map
```

Check `/api/status` for `map_available` and `track_available`. `/api/map.png` returns the locally rendered image.

### Port 80 is already in use

Do not force the 790T onto an unverified alternate HTTP port. Instead, give the robot another reachable LAN IP on which port 80 is available, for example a dedicated Docker/LXC host, and either run the core there or forward that IP's port 80 to the RobotBona HTTP service. Keep `20008` and `8090` reachable as required by your chosen topology.

## Standalone Docker / Proxmox deployment

The same core can run outside Home Assistant using the root `Dockerfile` or `docker-compose.example.yml`.

Required runtime values:

```text
ROBOTBONA_APP_KEY
ROBOTBONA_DEVICE_ID
```

Default container ports:

```text
18080/tcp  RobotBona HTTP/token service
20008/tcp  RobotBona TCP service
8090/tcp   local JSON API
```

For the tested firmware, map host port **80 → container port 18080**.

This topology can be useful if you want the robot-facing service to remain available while Home Assistant itself restarts.

## Local API

Read endpoints:

```text
GET /api/health
GET /api/status
GET /api/map
GET /api/map.png
```

Control endpoints:

```text
POST /api/start
POST /api/stop
POST /api/home
POST /api/map
POST /api/voice/on
POST /api/voice/off
POST /api/mode/{value}
POST /api/fan/{value}
```

The API deliberately redacts RobotBona auth codes, device IDs and tokens from client-facing state.

## From the original v4 proof-of-concept to this repository

The first working implementation was a single private `robotbona_local_service_v4.py` proof-of-concept. It had already demonstrated the critical real-hardware fact: the 790T could be pointed at a local replacement service and controlled without the live Proscenic/RobotBona cloud.

The repository turns that proof-of-concept into a maintainable system:

1. **Protocol extraction** — packet framing, login ACKs, normal ACKs, keepalive ACKs and control packets moved into dedicated protocol/command modules with byte-level regression tests.
2. **State model** — raw RobotBona values are retained while client-facing friendly labels stay intentionally conservative; credentials and large map blobs are excluded from public state.
3. **Reusable TCP/HTTP services** — the robot-facing HTTP token endpoint and persistent TCP session are reusable server components instead of one monolithic script.
4. **Command service** — start/stop/home/mode/fan/voice/map requests use one shared live robot connection and explicit capability/evidence metadata.
5. **Stable local API** — Home Assistant and other clients talk to `/api/...` instead of knowing proprietary RobotBona packets.
6. **Map pipeline** — RobotBona map/track payloads are decoded in the core and rendered to PNG server-side.
7. **Persistence/runtime** — one runtime starts HTTP, TCP, API and persistence services and reads secrets from runtime configuration instead of hard-coding private installation values.
8. **Container/App packaging** — the same runtime is packaged for Docker/Proxmox and as a Home Assistant App.
9. **Thin Home Assistant integration** — Home Assistant contains no RobotBona framing or command IDs; it polls the local API and exposes native entities.
10. **Hardware validation** — the refactored repository implementation was tested on the real robot for login/state, start, stop, return-to-dock, map/track and Home Assistant control. During that migration, the host-port-80 requirement was discovered and confirmed.

The sanitized monolithic baseline remains in `reference/` as a regression/reference artifact; the production architecture is the modular `src/robotbona/` implementation.

## Protocol notes

For commands with extra values, JSON field order matters on the tested firmware. Preserve the extra parameter **before** `transitCmd`, for example:

```json
{"mode":"4","transitCmd":"106"}
```

not:

```json
{"transitCmd":"106","mode":"4"}
```

See [`docs/confirmed-behavior.md`](docs/confirmed-behavior.md), [`docs/protocol.md`](docs/protocol.md), [`docs/api.md`](docs/api.md), [`docs/deployment.md`](docs/deployment.md) and [`docs/home-assistant.md`](docs/home-assistant.md) for deeper implementation notes.

## Repository layout

```text
reference/          sanitized monolithic proof-of-concept baseline
src/robotbona/      reusable RobotBona core/server and local API
custom_components/  Home Assistant custom integration (thin API client)
ha-app/             Home Assistant App packaging
docs/               protocol, API, deployment and integration notes
tests/              regression/boundary tests and sanitized fixtures
```

## Privacy / public-repository policy

Do **not** commit or post real device identifiers, MAC addresses, auth codes, Wi-Fi credentials, private IP assignments, packet captures, raw proxy logs or captured cloud/local tokens. Use sanitized fixtures and runtime configuration instead.

## Prior art and attribution

This project is an independent reverse-engineering effort and is not affiliated with Proscenic or RobotBona. Earlier community work, especially [`felix-engelmann/robotbona`](https://github.com/felix-engelmann/robotbona), helped establish parts of the RobotBona protocol and map decoding. See [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

Historical Home Assistant work in [`deblockt/hass-proscenic-790T-vacuum`](https://github.com/deblockt/hass-proscenic-790T-vacuum) was also useful as a behavioural reference. Protocol facts are independently verified where marked as confirmed.

## Disclaimer

Use at your own risk. Reverse-engineered behaviour can vary by firmware and hardware revision. Unknown status and error values are deliberately preserved rather than guessed.
