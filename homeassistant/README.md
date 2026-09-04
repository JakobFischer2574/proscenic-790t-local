# Home Assistant integration

This directory will contain the Home Assistant custom integration.

The integration must stay a **thin client** of the local RobotBona API. It should not duplicate proprietary packet framing, command IDs, map decoding or firmware-specific state semantics.

Planned entities include:

- vacuum entity: start, pause/stop, return to dock
- battery/status sensors
- cleaning-mode selector (only confirmed modes by default)
- fan selector based on confirmed capability data
- voice switch
- map/image entity
- diagnostics exposing raw state values where useful

Scheduling belongs in normal Home Assistant automations rather than the unconfirmed native robot scheduler.
