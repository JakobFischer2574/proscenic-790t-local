# Proscenic 790T Local — Home Assistant App

This App runs the same `robotbona` core/server image used by the standalone Docker deployment. There is no separate Home Assistant copy of the proprietary protocol implementation.

## Before starting

Enter the robot's `app_key` and `device_id` in the App configuration. Do not publish those values in issues or logs. The supplied local token is a generated 32-character dummy, not a captured cloud credential.

The App exposes three container ports:

- `18080/tcp` — robot-facing HTTP/token endpoint
- `20008/tcp` — robot-facing persistent RobotBona TCP connection
- `8090/tcp` — local JSON API

For the tested Wi-Fi firmware `1.0.41`, the robot-facing HTTP service must be presented on **host port 80**. The recommended/default host mappings are therefore:

- container `18080/tcp` → host `80`
- container `20008/tcp` → host `20008`
- container `8090/tcp` → host `8090`

Provisioning with `jPort=18080` was accepted by the robot but did not lead to a completed RobotBona login; reprovisioning with `jPort=80` immediately worked. Treat host port 80 as a tested firmware requirement unless another firmware has been independently verified.

## Robot provisioning

Provision the robot so that:

```text
jDomain = HOME_ASSISTANT_LAN_IP
jPort   = 80
sDomain = HOME_ASSISTANT_LAN_IP
sPort   = 20008
```

The provisioning response contains the robot's `deviceId` and `appKey`; copy those values into the App configuration and keep them private.

Do not assume a particular private subnet. The robot must be able to reach the Home Assistant host on both robot-facing ports.

## Persistence

Only public last-known state plus the latest map/track payload are persisted under `/data`. Session credentials are learned again from each robot login and are never persisted.

## API

After startup, `GET http://HOME_ASSISTANT_HOST:8090/api/health` reports service/robot connection health and `/api/status` returns public state/capabilities. The target result after successful robot login is `ok=true` and `connected=true`.

The custom Home Assistant integration consumes this API rather than implementing RobotBona itself.

## Security

The local API is intended for a trusted LAN and currently has no authentication layer. Do not expose the robot-facing ports or API port directly to the public internet.
