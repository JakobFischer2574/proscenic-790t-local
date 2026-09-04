# AGENTS.md

Instructions for Codex and other coding agents working in this repository.

## Architectural rule

The RobotBona protocol implementation is the authoritative layer.

The Home Assistant integration must remain a **thin client**. Do not move protocol semantics, robot capability knowledge, state interpretation, map decoding, packet construction or proprietary command handling into Home Assistant-only code.

Preferred dependency direction:

```text
robotbona core/server -> local API -> Home Assistant integration
```

Other clients must be able to use the core/server without Home Assistant.

## Protocol safety

Do not change empirically confirmed wire behaviour without an explicit reason, regression coverage and review.

Especially preserve:

- TCP service port semantics for RobotBona traffic.
- 20-byte packet framing.
- Login ACK magic and payload shape.
- Normal ACK and keepalive ACK framing.
- Server-to-robot control packet header/magic.
- Command sequence handling.
- `targetType` / control envelope unless new evidence proves otherwise.
- JSON insertion order for commands with extra values.

On the tested firmware, commands such as mode and fan require the extra field to be serialized **before** `transitCmd`:

```json
{"mode":"4","transitCmd":"106"}
```

Treat JSON key order here as wire-level behaviour, not cosmetic formatting.

## Evidence levels

Never invent protocol semantics.

Use these labels in documentation and code comments where useful:

- **confirmed** — observed on the tested physical Proscenic 790T and resulting robot behaviour/state change verified.
- **observed** — packet/state value captured, but meaning or effect not fully proven.
- **historical** — found in earlier third-party implementations/documentation but not yet verified on the tested firmware.
- **unknown** — meaning not established.

An ACK only proves that a packet was accepted syntactically. It does **not** by itself prove the requested function worked.

## Current confirmed commands

- `100` start
- `102` stop/pause
- `104` return to dock
- `106` cleaning mode
- `110` fan setting
- `123` voice on
- `125` voice off
- `131` map/status request

`139` set time has been observed/sent but is not confirmed to work.

Confirmed distinct cleaning modes on the tested firmware:

- `3` normal/default/random
- `4` edge
- `6` area

Do not expose `1`, `8`, `10`, or `11` as confirmed distinct modes unless new evidence establishes their behaviour on this firmware.

## State semantics

Do not blindly import historical enum names from other RobotBona devices or older Home Assistant code.

For the tested unit:

- `workState=1` is confirmed during active cleaning.
- `workState=2` is observed as pending/transitional/idle-like.
- `workState=4` is confirmed while returning/docking.
- `workState=5` has been physically observed while docked and charging.
- `workState=6` has been observed at the dock / with full battery, but its exact distinction from state 5 is not fully established.
- `workState=7` has been observed transiently; exact semantics are not established for this firmware.

Preserve raw state values in the core API even when a friendly interpretation is added.

## Public repository / privacy rules

Never commit real user- or device-specific data, including:

- device IDs
- MAC addresses
- auth codes
- Wi-Fi SSIDs or passwords
- private LAN IP assignments
- real cloud/local tokens
- packet captures (`.pcap`, `.pcapng`)
- raw proxy/service logs
- unredacted request fixtures

Use placeholders, sanitized fixtures and environment/configuration values.

Do not print secrets in normal logs.

## Third-party code

`felix-engelmann/robotbona` is MIT-licensed and may be used only with the required attribution/license notice.

`deblockt/hass-proscenic-790T-vacuum` is treated as a behavioural/historical reference only. Do not copy code from it unless a compatible license is independently established.

When adding code derived from another source, document the source and licensing in `THIRD_PARTY_NOTICES.md`.

## Development workflow

- Preserve the sanitized monolithic reference implementation under `reference/`.
- Refactor into `src/` incrementally rather than rewriting the protocol from scratch.
- Add regression tests before or alongside protocol refactors.
- Prefer captured **sanitized** byte fixtures for packet-level tests.
- Keep networking, protocol, state, map decoding, API and Home Assistant adapter concerns separated.
- Unknown fields must be preserved where practical rather than discarded.
- Avoid hard-coded installation-specific IPs and credentials.

## Home Assistant

The Home Assistant layer should consume the local API and map core state/capabilities to HA entities.

It may provide:

- vacuum controls
- battery/status sensors
- cleaning-mode selector
- fan selector
- voice switch
- map image/entity
- diagnostic raw-state attributes where appropriate

But Home Assistant must not become the only implementation of those concepts.
