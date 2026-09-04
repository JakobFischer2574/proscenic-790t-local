# Deployment

The same `robotbona` package/runtime is used by standalone Docker/Proxmox deployments and by the Home Assistant App. The Home Assistant layer does not carry a second protocol implementation.

## Standalone Docker / Proxmox

Use the root `Dockerfile` or `docker-compose.example.yml`. Supply `ROBOTBONA_APP_KEY` and `ROBOTBONA_DEVICE_ID` at runtime and mount `/data` for last-known state/map persistence. Listener ports are configurable through environment variables.

Default internal ports:

- `18080/tcp` RobotBona HTTP/token service
- `20008/tcp` RobotBona TCP service
- `8090/tcp` local JSON API

The container restarts cleanly after robot disconnects because the TCP listener remains available for the ESP8266 to reconnect. Container health is checked through `/api/health`.

## Home Assistant App

This repository is also a Home Assistant App repository (`repository.yaml`). The `ha-app/` manifest references the same GHCR image produced from the root Dockerfile. App configuration is read from Supervisor's `/data/options.json`; no secrets are baked into the image or repository.

The initial App image supports `amd64`, matching the intended Proxmox/Home Assistant OS deployment. Additional architectures can be added later with architecture-correct image metadata rather than publishing an unverified multi-architecture manifest.

The App exposes container ports through configurable host mappings in the Supervisor Network settings. Provision the robot with the Home Assistant host IP and the chosen host mappings for the robot-facing HTTP and TCP ports.

## Networking

The robot must be able to route to the service host. Do not assume a specific RFC1918 subnet. If Home Assistant and the robot are separated by guest-network isolation or firewall rules, allow the robot to reach the configured RobotBona HTTP and TCP host ports.

## Persistence

Only public state plus the latest map and track strings are stored. Login/session credentials are intentionally not persisted and are relearned on every RobotBona login.
