# Home Assistant integration

The custom integration is intentionally a **thin client** of the local API. It contains no RobotBona packet framing, command IDs, map decoding, state-code authority or device credentials.

## Installation

Copy `custom_components/proscenic_790t_local` into Home Assistant's `/config/custom_components/` directory and restart Home Assistant. Then open **Settings → Devices & services → Add integration → Proscenic 790T** and enter the host/IP and API port of the local server (default API port: `8090`).

The integration uses a UI config flow and local polling. Scheduling should be implemented with normal Home Assistant automations; the unconfirmed native robot timer/clock protocol is not exposed.

## Entities

The integration creates one device with:

- vacuum entity: start, stop/pause and return to dock
- battery sensor
- connection binary sensor
- conservative status sensor
- raw `workState`, `workMode` and error diagnostic sensors
- cleaning-mode select populated from **server capability metadata** and limited to modes the core marks confirmed
- fan select populated from server capability metadata
- optimistic voice switch; the tested firmware accepts voice on/off commands but does not report voice state, so Home Assistant marks this control as assumed state
- map image fetched from `/api/map.png`; RobotBona RLE/base64/track decoding is performed in the core/server, not in Home Assistant

Additional raw diagnostics are disabled by default to avoid unnecessary recorder noise.

## State mapping

The integration maps only conservative friendly state labels supplied by the server to Home Assistant's standardized vacuum activities. It does not duplicate proprietary numeric `workState` semantics. Raw values remain available as diagnostic sensors.

## API dependency

The custom integration requires the local server API from this repository. It does not connect to Proscenic or RobotBona cloud services and cannot directly replace the robot-facing server on its own.
