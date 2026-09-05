# Deployment

The same `robotbona` package/runtime is used by standalone Docker/Proxmox deployments and by the Home Assistant App. The Home Assistant layer does not carry a second protocol implementation.

## Standalone Docker / Proxmox

Use the root `Dockerfile` or `docker-compose.example.yml`. Supply `ROBOTBONA_APP_KEY` and `ROBOTBONA_DEVICE_ID` at runtime and mount `/data` for last-known state/map persistence. Listener ports are configurable through environment variables.

Default internal/container ports:

- `18080/tcp` RobotBona HTTP/token service
- `20008/tcp` RobotBona TCP service
- `8090/tcp` local JSON API

### Tested-firmware host-port requirement

On the tested Proscenic 790T Wi-Fi firmware `1.0.41`, the robot-facing HTTP service only completed the expected login flow when presented on **host port 80**. Provisioning with another `jPort` can return success without the subsequent RobotBona connection becoming active.

Recommended host mappings for the tested firmware:

```text
host 80    -> container 18080
host 20008 -> container 20008
host 8090  -> container 8090
```

Provision the robot with `jPort=80` and `sPort=20008` unless your firmware has been independently verified to support another HTTP host port.

The container restarts cleanly after robot disconnects because the TCP listener remains available for the ESP8266 to reconnect. Container health is checked through `/api/health`.

## Home Assistant App

This repository is also a Home Assistant App repository (`repository.yaml`). The `ha-app/` manifest references the same GHCR image produced from the root Dockerfile. App configuration is read from Supervisor's `/data/options.json`; no secrets are baked into the image or repository.

The initial App image supports `amd64`, matching the tested Proxmox/Home Assistant OS deployment. Additional architectures can be added later with architecture-correct image metadata rather than publishing an unverified multi-architecture manifest.

The App's default network mapping presents container port `18080` on host port `80`, container port `20008` on host `20008`, and the local API on host `8090`.

If host port 80 is already occupied, use another LAN IP/host for the robot-facing service or a dedicated LAN proxy/NAT rule that presents port 80 to the robot and forwards it to the HTTP service. Do not assume an unverified alternate `jPort` will work on firmware `1.0.41`.

## Networking

The robot must be able to route to the service host. Do not assume a specific RFC1918 subnet. If Home Assistant and the robot are separated by guest-network isolation or firewall rules, allow the robot to reach the configured RobotBona HTTP and TCP host ports.

The API on `8090` is intended for a trusted LAN. Do not expose the RobotBona or API ports directly to the public internet.

## Persistence

Only public state plus the latest map and track strings are stored. Login/session credentials are intentionally not persisted and are relearned on every RobotBona login.
