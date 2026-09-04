# Home Assistant App packaging

This directory is reserved for packaging the RobotBona local server as a Home Assistant App.

The app should run the robot-facing service in its own process/container and expose a local API consumed by the custom integration.

Robot-facing ports must be configurable to avoid collisions with Home Assistant itself. A deployment may, for example, use a high HTTP port for the emulated token service while retaining/configuring the RobotBona TCP port separately.

The same core/server must also remain deployable outside Home Assistant, e.g. in a dedicated Proxmox LXC/container.
