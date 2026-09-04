# RobotBona protocol notes for the Proscenic 790T

This document records protocol behaviour relevant to the tested Proscenic 790T. It intentionally distinguishes empirically confirmed behaviour from historical/community information.

## Tested device / firmware

- Model: Proscenic 790T
- Wi-Fi module firmware: `1.0.41`
- MCU firmware: `1.8.2614(828)`

Device-specific identifiers and credentials are intentionally omitted from this public repository.

## Provisioning / SoftAP

In provisioning mode the robot exposes a `Proscenic_...` SoftAP. The robot is reachable at `192.168.4.1` from a client associated with that access point.

Observed provisioning request:

```text
GET /robot/getRobotInfo.do
    ?ssid=<url-encoded-ssid>
    &pwd=<url-encoded-password>
    &jDomain=<local-http-server-host>
    &jPort=<local-http-server-port>
    &sDomain=<local-tcp-server-host>
    &sPort=<local-tcp-server-port>
    &cleanSTime=5
User-Agent: blapp
```

Historically the vendor endpoints used separate HTTP (`jDomain`/`jPort`) and persistent TCP (`sDomain`/`sPort`) destinations. The local replacement uses the same arrangement.

The tested ESP8266 is 2.4-GHz-only. SSIDs without spaces were more reliable during testing; treat that as an operational observation rather than a protocol requirement.

## HTTP token service

After joining the configured Wi-Fi network the robot POSTs to:

```text
/baole-web/common/getToken.do
```

The vendor response that was captured used:

- HTTP/1.1
- `Content-Type: application/json;charset=UTF-8`
- `Transfer-Encoding: chunked`
- `Connection: close`

A cloud-style response body has the shape:

```json
{
  "msg": "ok",
  "result": "0",
  "data": {
    "appKey": "<app-key>",
    "deviceNo": "<device-id>",
    "token": "<32-character-token>"
  },
  "version": "1.0.0"
}
```

On the tested firmware an arbitrary locally generated 32-character token worked. No live vendor cloud validation was required for the tested runtime functionality.

The robot also POSTs to:

```text
/baole-web/common/uploadLog.do
```

The current local baseline acknowledges this endpoint but does not yet use the uploaded payload diagnostically.

## Persistent TCP service

The active control/status transport on the tested firmware is a persistent outbound TCP connection from the robot to the configured `sDomain:sPort`. The commonly observed/default port is `20008`.

The JSON `devicePort` advertised by the robot may still contain `8888`, but direct old-style local control on TCP 8888 was not successful on the tested firmware. Do not probe 8888 as part of the normal local-control path.

### Frame layout

RobotBona frames use a 20-byte header followed by an optional payload:

```text
Offset  Size  Meaning
0       4     total frame length, little-endian uint32
4       4     message magic/type
8       4     middle/control bytes
12      4     sequence number, little-endian uint32
16      4     flag bytes
20      ...   payload
```

The total length includes the 20-byte header.

JSON payloads are compact and terminated with `\n` in the current working implementation.

### Login

The robot sends a JSON login containing values such as token, device ID, auth code, device IP/port and firmware information.

The working local server replies with a login ACK using magic:

```text
11 00 c8 00
```

and a payload equivalent to:

```json
{"msg":"login succeed","result":0,"version":"1.0","time":"YYYY-MM-DD-hh-mm-ss"}
```

### Normal ACK

For ordinary robot-originated data packets, the working local server uses magic:

```text
19 00 c8 00
```

with a payload equivalent to:

```json
{"msg":"OK","result":0,"version":"1.0"}
```

### Keepalive ACK

Empty/20-byte keepalive traffic is acknowledged using magic:

```text
11 01 c8 00
```

with the observed flag value:

```text
e7 03 00 00
```

## Server-to-robot control packets

The working control frame uses:

```text
magic:   fa 00 c8 00
middle:  00 00 09 01
flag:    00 00 00 00
```

Robot command responses have been observed with magic:

```text
fa 00 00 00
```

and the matching command sequence number.

A typical control payload shape is:

```json
{
  "cmd": 0,
  "control": {
    "authCode": "<learned-at-login>",
    "deviceIp": "<learned-at-login>",
    "devicePort": "8888",
    "targetId": "0",
    "targetType": "3"
  },
  "seq": 0,
  "value": {
    "transitCmd": "100"
  }
}
```

The tested robot accepted `targetId="0"` and `targetType="3"`.

### JSON order is significant for parameterized commands

On the tested firmware, command `106` (mode) and `110` (fan) only produced the expected behaviour when the extra parameter was serialized before `transitCmd`.

Working examples:

```json
{"mode":"4","transitCmd":"106"}
```

```json
{"fan":"3","transitCmd":"110"}
```

Do not treat key order as a stylistic detail in packet-building code.

## Confirmed commands

| `transitCmd` | Function | Evidence |
|---:|---|---|
| `100` | start cleaning | physical behaviour + state transition |
| `102` | stop/pause | physical behaviour + state transition |
| `104` | return to dock | physical behaviour + state transition |
| `106` | cleaning mode | distinct mode/state changes confirmed for values 3/4/6 |
| `110` | fan setting | state changes confirmed for tested values |
| `123` | voice on | physical behaviour confirmed |
| `125` | voice off | physical behaviour confirmed |
| `131` | map/status request | map/status traffic observed |
| `139` | set clock | packet sent; effect not confirmed |

See `confirmed-behavior.md` for device-specific interpretation.

## Robot-originated status

### `noteCmd = "102"`

Status packets have included fields such as:

```text
workState
workMode
battery
fan
error
direction
brush
```

Preserve raw values. Friendly state labels must remain firmware-aware and should not overwrite the raw protocol state.

### `noteCmd = "101"`

Cleaning/map packets have included fields such as:

```text
clearArea
clearTime
clearSign
clearModule
map
track
```

## Map / track encoding

Current reverse-engineering notes:

### Track

- Base64 decode.
- Skip the first 4 bytes.
- Remaining bytes form signed X/Y byte pairs.

### Map

- Base64 decode.
- Skip the first 9 bytes.
- Logical raster size observed as 100 x 100.
- RLE: values with top two bits `11` encode a repeat count for the following normal byte.
- A normal byte encodes four 2-bit pixels.
- Observed 2-bit meanings:
  - `00`: unknown
  - `10`: floor
  - `01`: wall

Map orientation/overlay details should be treated independently from the raw decoder and validated visually.

## Unknowns / cautions

- Exact semantic distinction between `workState=5` and `workState=6` is not fully established on this firmware.
- Historical enum labels from older integrations are not authoritative for this unit.
- ACK receipt alone does not prove a command had a functional effect.
- Native scheduling/timer protocol has not been fully reverse-engineered and is not required for Home Assistant scheduling.
- OTA and other special cloud functions are outside the demonstrated cloudless scope.
