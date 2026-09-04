# Proscenic 790T Local — Home Assistant App

This App runs the same `robotbona` core/server image used by the standalone Docker deployment. There is no separate Home Assistant copy of the proprietary protocol implementation.

## Before starting

Enter the robot's `app_key` and `device_id` in the App configuration. Do not publish those values in issues or logs. The supplied local token is a generated 32-character dummy, not a captured cloud credential.

The App exposes three host ports by default:

- `18080/tcp` — robot-facing HTTP/token endpoint
- `20008/tcp` — robot-facing persistent RobotBona TCP connection
- `8090/tcp` — local JSON API

The host-side port mappings can be changed in the App's Network settings. If you change the robot-facing mappings, provision the robot with those reachable host ports.

## Robot provisioning

Provision the robot so that its RobotBona HTTP destination points to the Home Assistant host IP and the host port mapped to container port `18080`, and its RobotBona TCP destination points to the same host IP and the host port mapped to container port `20008`.

Do not assume a particular private subnet. The robot must be able to reach the Home Assistant host on both ports.

## Persistence

Only public last-known state plus the latest map/track payload are persisted under `/data`. Session credentials are learned again from each robot login and are never persisted.

## API

After startup, `GET http://HOME_ASSISTANT_HOST:8090/api/health` reports service/robot connection health and `/api/status` returns public state/capabilities. The custom Home Assistant integration consumes this API rather than implementing RobotBona itself.
