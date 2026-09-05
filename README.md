# proscenic-790t-local

Fully local, cloudless control for the **Proscenic 790T** vacuum robot by replacing the RobotBona services it expects on the local network.

> **Status:** hardware-tested on a real Proscenic 790T with Wi-Fi firmware `1.0.41` and MCU firmware `1.8.2614(828)`. The tested path covers local RobotBona login/state, start, stop, return-to-dock, cleaning modes, fan control, map/track decoding, the local API, the Home Assistant integration, and the Home Assistant App deployment.
>
> This is still a reverse-engineering project. Other firmware or hardware revisions may behave differently.

## Read this first: there are two Home Assistant pieces

This repository contains **two separate components**, and a normal Home Assistant installation needs both:

1. **Proscenic 790T Local App** — the local RobotBona replacement. This is the server the robot talks to.
2. **Proscenic 790T custom integration** — the Home Assistant UI/device layer. It talks only to the App's local API.

```text
Proscenic 790T
    |
    | HTTP :80 + RobotBona TCP :20008
    v
Proscenic 790T Local App / server
    |- token endpoint
    |- TCP login / ACK / keepalive
    |- commands
    |- state + capability metadata
    |- map / track decoding
    `- local API :8090
          |
          v
Home Assistant custom integration
    |- vacuum entity
    |- battery / status sensors
    |- cleaning-mode / fan selects
    |- voice switch
    `- map image
```

The Home Assistant integration deliberately contains **no proprietary RobotBona packet implementation**. The core/server is authoritative and the integration is only a thin local API client.

## Important firmware quirk: robot HTTP must be reachable on host port 80

On the tested firmware, provisioning with a different `jPort` could return success while the robot still failed to complete the subsequent local RobotBona login.

The working mapping is:

```text
robot HTTP     HOME_ASSISTANT_IP:80    -> App/container :18080
robot TCP      HOME_ASSISTANT_IP:20008 -> App/container :20008
local API      HOME_ASSISTANT_IP:8090  -> App/container :8090
```

The App listens internally on `18080`, but Home Assistant must publish that service to the robot as **host port 80** on the tested firmware.

If port 80 is already occupied, do not assume another `jPort` will work. A safer topology is to run the server on another LAN IP, for example a small Proxmox/LXC/Docker host, or use a dedicated LAN proxy/NAT rule that presents port 80 to the robot and forwards it to the RobotBona HTTP service.

## Tested device and confirmed functions

Tested firmware:

- Wi-Fi module: `1.0.41`
- MCU: `1.8.2614(828)`

Confirmed commands on the tested robot:

| Command | Meaning | Evidence |
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

Confirmed cleaning modes:

| Value | Behaviour | Evidence |
|---:|---|---|
| `3` | normal/default/random cleaning | confirmed |
| `4` | edge cleaning | confirmed |
| `6` | area cleaning | confirmed |
| `1`, `8`, `10`, `11` | accepted/observed but no distinct behaviour proven on this firmware | observed only |

Confirmed fan values are `2` (normal) and `3` (turbo). Values `1` and `4` have been observed but are not treated as equally well confirmed.

Map and track payloads are decoded locally and rendered to PNG by the server.

---

# Recommended installation: Home Assistant OS / Supervised

The current Home Assistant App image supports **`amd64`**.

## Prerequisites

You need:

- a Proscenic 790T;
- Home Assistant OS or Supervised on `amd64` for the App path below;
- the robot and Home Assistant on mutually reachable LANs — the same LAN is simplest;
- 2.4 GHz Wi-Fi for the robot's ESP8266;
- host ports `80`, `20008`, and `8090` reachable on the Home Assistant host;
- a computer or phone that can temporarily join the robot's setup Wi-Fi.

**Strongly recommended:** give the Home Assistant host a stable LAN IP, for example with a DHCP reservation. The robot is provisioned with that IP and will stop reaching the local server if the address later changes.

Do **not** expose ports `80`, `20008`, or `8090` to the public internet. The local API is designed for a trusted LAN and currently has no authentication layer.

## Step 1 — Add this repository to the Home Assistant App store

In Home Assistant open:

**Settings → Apps → App store / Install app → ⋮ → Repositories**

Add:

```text
https://github.com/JakobFischer2574/proscenic-790t-local
```

Install **Proscenic 790T Local**.

## Step 2 — Check the App network mappings

Open **Proscenic 790T Local → Network** and use:

```text
container 18080/tcp -> host 80
container 20008/tcp -> host 20008
container 8090/tcp  -> host 8090
```

The `18080 -> 80` mapping is intentional.

After the App is running, you can verify the ports from another LAN machine:

```powershell
Test-NetConnection YOUR_HOME_ASSISTANT_LAN_IP -Port 80
Test-NetConnection YOUR_HOME_ASSISTANT_LAN_IP -Port 20008
Test-NetConnection YOUR_HOME_ASSISTANT_LAN_IP -Port 8090
```

All three should report:

```text
TcpTestSucceeded : True
```

## Step 3 — Put the robot into Wi-Fi/setup mode

Put the 790T into its normal Wi-Fi pairing / SoftAP mode using the robot's normal pairing procedure.

It should expose a network similar to:

```text
Proscenic_XXXXXX
```

Connect your computer to that network. The robot is normally available at:

```text
192.168.4.1
```

## Step 4 — Provision the robot and obtain `deviceId` + `appKey`

The provisioning response contains the robot's `deviceId` and `appKey`. Treat both as private runtime configuration. Do not commit them to Git or paste them into public issues.

The following PowerShell sequence is hardware-tested:

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

Expected result code:

```text
0
```

`result = 0` means the robot accepted the provisioning request. It does **not** prove that the subsequent RobotBona HTTP/TCP login completed.

### First-time setup note

There is a small chicken-and-egg problem for a completely fresh installation: the App wants `deviceId` and `appKey`, while the easiest way to read those values is the provisioning response above.

That is fine:

1. provision once to obtain the values;
2. configure/start the App with those values;
3. if the robot did not reconnect automatically, power-cycle it or repeat the provisioning request once more.

## Step 5 — Configure and start the Home Assistant App

Open **Proscenic 790T Local → Configuration** and enter:

```yaml
app_key: "YOUR_APP_KEY"
device_id: "YOUR_DEVICE_ID"
local_token: "LOCAL790T00000000000000000000000"
persist_interval: 5
```

The supplied `local_token` is a generated local dummy token of the required 32-character length. It is **not** a captured vendor-cloud credential and can be left unchanged for the initial setup.

Start the App.

## Step 6 — Verify that the robot actually logged in

From another machine on the LAN:

```powershell
Invoke-RestMethod http://YOUR_HOME_ASSISTANT_LAN_IP:8090/api/health
```

The target state is:

```text
ok   connected
--   ---------
True True
```

If you get `True False`, the App/API is running but the robot has not completed its local RobotBona login yet.

Inspect the public state with:

```powershell
Invoke-RestMethod http://YOUR_HOME_ASSISTANT_LAN_IP:8090/api/status | ConvertTo-Json -Depth 10
```

A connected robot should report values such as battery, work state, fan state and firmware data. Credentials are redacted from client-facing API state.

## Step 7 — Install the custom Home Assistant integration

HACS installation is **not yet provided**. Install the integration manually by copying:

```text
custom_components/proscenic_790t_local
```

into the Home Assistant custom-components directory.

Canonical Home Assistant path:

```text
/config/custom_components/proscenic_790t_local
```

Some Home Assistant file-management Apps expose the same configuration root as `/homeassistant`. For example, with the **File editor** App and Git enabled:

```sh
rm -rf /tmp/proscenic-790t-local
git clone --depth 1 https://github.com/JakobFischer2574/proscenic-790t-local.git /tmp/proscenic-790t-local
mkdir -p /homeassistant/custom_components
rm -rf /homeassistant/custom_components/proscenic_790t_local
cp -r /tmp/proscenic-790t-local/custom_components/proscenic_790t_local /homeassistant/custom_components/
```

If your environment exposes the Home Assistant configuration root as `/config`, replace `/homeassistant` with `/config`.

Restart Home Assistant completely after copying the integration.

## Step 8 — Add the Proscenic integration

Go to:

**Settings → Devices & services → Add integration → Proscenic 790T**

Enter:

```text
Host: YOUR_HOME_ASSISTANT_LAN_IP
Port: 8090
```

Use the Home Assistant host's LAN IP, **not** `127.0.0.1`.

The integration creates one device with entities including:

- vacuum entity: start, stop/pause, return to dock;
- battery sensor;
- connectivity binary sensor;
- conservative friendly status sensor;
- raw diagnostic sensors;
- cleaning-mode select populated from confirmed server capability metadata;
- fan select;
- voice switch — assumed state because the tested firmware accepts voice commands but does not report a reliable voice state;
- map image.

## Step 9 — Functional test

Test **Start**, **Stop/Pause**, and **Return to dock** from Home Assistant.

You can also test the same server directly:

```powershell
Invoke-RestMethod -Method Post http://YOUR_HOME_ASSISTANT_LAN_IP:8090/api/start
Invoke-RestMethod -Method Post http://YOUR_HOME_ASSISTANT_LAN_IP:8090/api/stop
Invoke-RestMethod -Method Post http://YOUR_HOME_ASSISTANT_LAN_IP:8090/api/home
Invoke-RestMethod -Method Post http://YOUR_HOME_ASSISTANT_LAN_IP:8090/api/map
```

Then inspect:

```powershell
$r = Invoke-RestMethod http://YOUR_HOME_ASSISTANT_LAN_IP:8090/api/status
$r.status.state
$r.status.friendly
$r.status.map_available
$r.status.track_available
```

Map PNG:

```text
http://YOUR_HOME_ASSISTANT_LAN_IP:8090/api/map.png
```

---

# Troubleshooting

## `/api/health` works but `connected` stays `false`

Check:

- the robot returned to the normal Wi-Fi after provisioning;
- the robot can reach the Home Assistant host;
- host port `80` is open;
- host port `20008` is open;
- the App is running with the correct `app_key` and `device_id`;
- the robot was provisioned with `jPort=80` and `sPort=20008`;
- guest/client isolation or firewall rules are not blocking robot → Home Assistant traffic.

The most important tested-firmware gotcha is **port 80**. During hardware testing, provisioning with `jPort=18080` returned success, but the robot never completed login. Reprovisioning with `jPort=80` immediately produced `connected=true`.

## The integration does not appear in Home Assistant

Check that:

- the directory is exactly `proscenic_790t_local`;
- `manifest.json` is directly inside that directory;
- Home Assistant was fully restarted after copying the integration.

A YAML reload is not enough for a newly added custom integration.

## The map is unavailable

Request a map refresh:

```powershell
Invoke-RestMethod -Method Post http://YOUR_HOME_ASSISTANT_LAN_IP:8090/api/map
```

Then inspect:

```powershell
$r = Invoke-RestMethod http://YOUR_HOME_ASSISTANT_LAN_IP:8090/api/status
$r.status.map_available
$r.status.track_available
```

If map data exists, `/api/map.png` returns the locally rendered PNG.

## Port 80 is already occupied

The tested 790T firmware should be assumed to require robot-facing HTTP on port 80 until proven otherwise for a specific firmware revision.

Practical alternatives:

- run the RobotBona server on a different LAN host/IP;
- use a small Proxmox/LXC/Docker instance with port 80 available;
- use a LAN proxy/NAT rule that presents `IP:80` to the robot and forwards it to the server's RobotBona HTTP listener.

## Home Assistant was previously pointed at a PC/server

The current config flow identifies the integration by `host:port` and does not provide a dedicated reconfigure flow. Remove the old Proscenic integration entry and add it again with the new API host/IP.

## Updating the custom integration

Pull a fresh copy of the repository, replace `/custom_components/proscenic_790t_local`, and restart Home Assistant. The File editor command sequence from Step 7 can be reused.

---

# Standalone Docker / Proxmox deployment

The same core can run outside Home Assistant using the root `Dockerfile` or `docker-compose.example.yml`.

Required runtime values:

```text
ROBOTBONA_APP_KEY
ROBOTBONA_DEVICE_ID
```

Default container ports:

```text
18080/tcp  RobotBona HTTP/token service
20008/tcp  RobotBona persistent TCP service
8090/tcp   local JSON API
```

For the tested firmware, publish **host port 80 → container port 18080**.

A dedicated Proxmox/LXC/Docker deployment can be useful if you want the robot-facing service to remain available while Home Assistant itself restarts.

---

# Local API

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

The API intentionally redacts RobotBona auth codes, device IDs and tokens from public status snapshots.

---

# Repository layout

```text
reference/          sanitized reverse-engineering reference material
src/robotbona/      reusable RobotBona core/server + local API
custom_components/  Home Assistant custom integration
ha-app/             Home Assistant App packaging
docs/               protocol, deployment and integration notes
tests/              regression, API, map and HA-boundary tests
```

# Development principles

- Do not invent protocol semantics.
- Keep raw/unknown values available.
- Treat a protocol ACK as proof of transport acceptance, not automatically proof of physical effect.
- Preserve empirically required JSON field ordering.
- Distinguish `confirmed`, `observed`, `historical`, and `unknown` evidence.
- Never commit real Wi-Fi credentials, device identifiers, auth codes, tokens, private IP assignments, packet captures or raw proxy logs.
- Keep the Home Assistant integration as a thin client of the local API.

# CI / validation

The repository includes automated tests for the protocol, commands, state model, local API, runtime/persistence, map decoding, and the Home Assistant architectural boundary. Home Assistant `hassfest` validation is also run in CI.

HACS distribution is **not currently enabled**. Repository-level publication requirements such as project licensing/metadata/branding should be resolved before advertising HACS support.

# Prior art and attribution

This project is an independent reverse-engineering effort and is not affiliated with Proscenic or RobotBona.

Earlier community work, especially [`felix-engelmann/robotbona`](https://github.com/felix-engelmann/robotbona), helped establish parts of the RobotBona protocol and map decoding. See [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) for attribution and licensing details.

Historical Home Assistant work in [`deblockt/hass-proscenic-790T-vacuum`](https://github.com/deblockt/hass-proscenic-790T-vacuum) was used only as a behavioural/historical reference where appropriate.

# Disclaimer

Use at your own risk. This is reverse-engineered behaviour and can vary by firmware/hardware revision. Unknown status and error values must not be guessed or presented as authoritative.