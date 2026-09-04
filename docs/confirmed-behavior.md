# Confirmed behaviour on the tested Proscenic 790T

This file records what was actually observed on the physical test unit. It is intentionally conservative: protocol acceptance and functional confirmation are different evidence levels.

## Evidence terminology

- **confirmed** — physical behaviour and/or an unambiguous state change was verified on the robot.
- **observed** — value/packet was captured, but its exact semantic meaning is not fully established.
- **historical** — found in older community implementations or captures, not independently proven on this firmware.
- **unknown** — insufficient evidence.

## Commands

### Start — `transitCmd=100`

**Confirmed.**

Observed sequence after starting included transitions such as:

```text
workState 6 -> 2 -> 1
```

with cleaning physically beginning. Command ACK/state reporting can precede the actual state transition.

### Stop/pause — `transitCmd=102`

**Confirmed.**

The robot stopped cleaning and later reported a transition away from active cleaning, commonly toward `workState=2`.

### Return to dock — `transitCmd=104`

**Confirmed.**

The robot physically returned to the charging station. `workState=4` was observed during return/docking.

### Voice — `transitCmd=123` / `125`

**Confirmed.**

- `123`: voice/sounds on
- `125`: voice/sounds off

Physical audio behaviour changed on the tested unit.

### Map request — `transitCmd=131`

**Confirmed as a usable protocol operation.**

Map/track data is also pushed by the robot during cleaning. The command can be used to request map/status-related traffic.

### Set clock — `transitCmd=139`

**Not confirmed.**

The observed/requested payload format is:

```json
{"set_time":"YYYYMMDDhhmm000x","transitCmd":"139"}
```

where `x` has been seen/tested as `0`, `1`, or `2`. The exact meaning of the final digit is unknown, and no reliable functional confirmation was obtained. Do not expose this as a proven feature.

## Cleaning modes — `transitCmd=106`

Parameterized command JSON must preserve the mode field before `transitCmd`:

```json
{"mode":"4","transitCmd":"106"}
```

### Mode `3` — normal/default/random

**Confirmed.**

Normal cleaning runs repeatedly report `workMode=3`. Treat this as the tested unit's normal/default cleaning mode.

### Mode `4` — edge

**Confirmed.**

Sending mode `4` produced a distinct mode transition and physical behaviour. A sequence such as the following was observed:

```text
workState=1 workMode=3 fan=2
-> transient pending-like state
-> workState=1 workMode=4 fan=3
```

`clearModule="4"` was also observed later during this mode.

### Mode `6` — area

**Confirmed.**

Sending mode `6` resulted in `workMode=6` during cleaning.

### Modes `1`, `8`, `10`, `11`

**Protocol-accepted but not functionally confirmed as distinct modes on this firmware.**

The robot acknowledged commands, but subsequent operation returned/remained at `workMode=3`. Do not present these values to users as confirmed cleaning modes for this firmware.

## Fan — `transitCmd=110`

Parameterized command JSON must preserve the fan field before `transitCmd`:

```json
{"fan":"3","transitCmd":"110"}
```

### Fan `2`

**Confirmed.** Subsequent state reported `fan=2`.

### Fan `3`

**Confirmed.** Subsequent state reported `fan=3`.

### Fan `1`

Observed in docked/pending contexts and accepted by the protocol. Treat exact user-facing naming with care until explicitly tested as an active-cleaning setting.

### Fan `4`

Not yet independently confirmed by a clear state/physical test on this unit. Do not claim it as confirmed merely because historical implementations name it `eco`.

## Mode/fan interaction

Mode changes can alter the operating fan value. Observed examples include:

```text
mode 3 -> fan 2
mode 4 -> fan 3
mode 6 -> fan 2
```

Therefore the core should expose both raw/current mode and fan values and should not assume that a fan selection is invariant across mode changes.

## Work states

Historical community code used names such as CLEANING, PENDING, RETURN_TO_BASE, NEAR_BASE and CHARGING. Those names are not copied as authoritative semantics here because the tested firmware behaves differently in some cases.

### `workState=1`

**Confirmed:** active cleaning.

### `workState=2`

**Observed:** pending/transitional/idle-like state. It occurs around start/stop/mode transitions.

### `workState=4`

**Confirmed:** return-to-dock/docking movement.

### `workState=5`

**Confirmed to occur while physically docked and charging.**

The robot was moved slightly away from the dock, drove itself back, audibly announced charging, then reported state `5` while battery percentage subsequently increased. Therefore historical labels such as `NEAR_BASE` are insufficient for this firmware.

### `workState=6`

**Observed at the dock / at full battery.**

The precise distinction from state `5` is not yet established. A Home Assistant adapter should not invent a definitive semantic label without additional evidence.

### `workState=7`

**Observed transiently.** Exact meaning is not established on this firmware.

## Battery

The `battery` field behaves as a 0–100-style percentage value. Values of `100` were observed in original-cloud captures and in local operation.

One test session showed an abrupt change from the high 90s to a very low value after an apparent device/module reset, followed by normal upward charging progression. This is treated as a device/gauge observation, not a protocol reinterpretation. The core should preserve the raw value rather than hiding it with aggressive plausibility filtering.

## Map lifecycle

During cleaning, `noteCmd=101` map/track data grows over the run. `clearSign` changes between cleaning sessions and a new session can begin with an effectively fresh map. A UI may preserve the last completed map while a new map is being built, but the core must distinguish stored presentation state from current robot-originated state.

No ability to inject a map back into the robot has been demonstrated.
