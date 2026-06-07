# Dreame AP10 Cloud API Analysis

Device model: `dreame.airp.u2507` (Pet Air Purifier AP10)

Last updated: 2026-06-07

This is the technical reference for the Dreame AP10 cloud API as used by this
integration: the MiOT property/action map, the power-control commands, and the
probing tools used to reverse-engineer it. Everything here was confirmed against
a live device on the `eu` server.

## Power Control

Power is the one area of the AP10 that does not behave like a normal MiOT
property, so it gets its own section.

The device reports its power state at `siid=2 piid=1` (`1=on`, `2=standby`), but
that property is **not directly writable** — `set_properties` on it either times
out or returns a success code while doing nothing. Power has to go through
actions instead, and the two directions use *different* actions:

| Direction | Command | Result |
| --- | --- | --- |
| **ON / wake** | `action siid=2 aiid=1 in=[{"piid": 1, "value": 1}]` | `2/1` flips `2 -> 1`, previous mode and fan level preserved |
| **OFF / standby** | `action siid=2 aiid=3` (no input) | `2/1` flips `1 -> 2` |

Notes confirmed by live testing:

- `aiid=1` is a set-power action that takes the target power as an input
  property. In practice it only powers the device **on** — calling it with
  `value=2` does not move the device to standby — so OFF stays on `aiid=3`.
- Waking with `aiid=1` restores the device's previous mode and fan level, the
  same as the Dreamehome app. The integration does not force a mode on turn-on.
- The OFF action `aiid=3` consistently echoes `aiid=9` back in its response
  (`{"siid":2,"aiid":9,"code":0}`). This is cosmetic; OFF still works.
- While the device is in standby, *all* property writes are silently no-op'd:
  they return `code 0` but never reach the device, and `2/1` stays `2`. This is
  why a one-way OFF (with no working wake command) left the device unrecoverable
  from Home Assistant.
- Power state lags after a wake or standby command — `2/1` can still report the
  old value for several seconds. The integration sets the new state optimistically
  and applies a stale-read grace window to `2/1` (the same mechanism used for the
  switch properties), so a poll that lands mid-transition does not flicker the
  Home Assistant toggle back to its previous state. Once the device reports the
  expected value, or the grace window expires, the real polled state takes over.

### How the wake command was found

Earlier probing missed `aiid=1` with an input value because it had only tried
`aiid=3` *with* the `{piid:1,value:1}` input and `aiid=1` *without* any input.
Enumerating the `siid=2` action space while the device was in standby — calling
each `aiid` with `in=[{"piid":1,"value":1}]` and watching `2/1` — surfaced it
immediately. Two full OFF → ON round-trips then confirmed it is reliable.

For the record, these attempts did **not** wake the device (all left `2/1=2`):

- `set_properties` on `siid=2 piid=1` with integer `1`, JSON `true`, and with/without an inner per-property `did`.
- Bare actions `siid=2 aiid=1/2/3/9` (no input).
- `siid=2 aiid=3` with input `{"piid":1,"value":1}` and `{"piid":1,"value":true}`.
- Legacy raw methods `set_power` (`"on"`/`true`/`1`) and `set_prop` (`["power","on"]`, `["on",true]`).
- App-like header variants (`User-Agent: Dart/3.2 (dart:io)`, `Dreame-Auth: bearer <token>`, `Dreame-Meta: cv=i_829`).

## Confirmed Property Matrix

| Control | siid | piid / aiid | Type | Values / notes |
| --- | ---: | ---: | --- | --- |
| Power state | 2 | piid 1 | Read-only state | `1=on`, `2=standby`. Not writable — control via actions (see Power Control). |
| Power ON | 2 | aiid 1 | Action | `in=[{"piid":1,"value":1}]` wakes the device. |
| Power OFF | 2 | aiid 3 | Action | No input; puts the device into standby. |
| Mode | 2 | piid 3 | Select / preset | `0=AI Purify`, `1=Strong Purification`, `2=Sleep Purification`, `3=Custom Mode`, `4=Pet Purify`. |
| Fan speed | 2 | piid 4 | Number | `1-5`. Writing a fan level forces the device into Custom Mode (`2/3=3`). |
| Voice Control Volume | 2 | piid 5 | Number / select | `80=minimum`, `90=moderate`, `100=high`. |
| LED color | 2 | piid 6 | Select | `-1=off`, `0=blue`, `1=orange`, `2=green`. |
| Keypress tone | 2 | piid 7 | Toggle | `0=off`, `1=on`. |
| Air quality level | 3 | piid 4 | Read-only sensor | Numeric AQ index. |
| PM2.5 | 3 | piid 5 | Read-only sensor | µg/m³. |
| Filter life percent | 4 | piid 1 | Read-only sensor | `0-100%` remaining. |
| Filter days left | 4 | piid 2 | Read-only sensor | Remaining filter days. |
| Filter used time | 4 | piid 3 | Read-only sensor | Hours on the current filter. |
| Filter reset | 4 | aiid 1 | Action | Resets the filter lifetime counter. |
| Device location | 6 | piid 3 | Read-only string | User-set location from the Dreamehome app. |
| Child lock | 6 | piid 5 | Toggle | `0=off`, `1=on`. |
| Play mode | 6 | piid 6 | Toggle | Cat play mode. |
| Voice Control | 6 | piid 7 | Toggle | Corrected from an earlier "Negative Ion + UVC" guess. |
| Timer | 6 | piid 8 | Number / timer | `0=off`; non-zero values set the timer in hours (`1-12`). |
| Service-7 candidate | 7 | piid 7 | Candidate toggle | Unidentified; keep debug-only. |

### Mode and fan-speed behavior

- Mode (`2/3`) writes are reliable in both directions while the device is on.
- Writing a fan speed (`2/4`) automatically switches the device to Custom Mode
  (`2/3=3`), so a "Sleep mode at a specific fan level" state cannot be set in a
  single call.
- Reads immediately after a mode change can occasionally return no values while
  the device transitions; a retry a few seconds later succeeds. Control paths
  should be optimistic rather than treating one empty poll as a failure.

## Connection

The integration talks to the Dreame Cloud API (`https://<region>.iot.dreame.tech:13267`),
the same cloud path the Dreamehome app uses. There is no local API for this
device. Login uses the Dreamehome account credentials; commands and polling all
go through the cloud.

## Property Probing

`scripts/probe_property.py` can read or write raw properties, scan ranges, and
trace which property an app setting changes.

```bash
# Read one property
uv run --with requests python scripts/probe_property.py --country eu --username "YOUR_EMAIL" --password "YOUR_PASSWORD" --siid 6 --piid 8

# Write one property
uv run --with requests python scripts/probe_property.py --country eu --username "YOUR_EMAIL" --password "YOUR_PASSWORD" --siid 6 --piid 8 --value 2

# Scan a range of services/properties
uv run --with requests python scripts/probe_property.py --country eu --username "YOUR_EMAIL" --password "YOUR_PASSWORD" --scan-siids 2-8 --scan-piids 1-12

# Read the focused filter/voice-control candidates
uv run --with requests python scripts/probe_property.py --country eu --username "YOUR_EMAIL" --password "YOUR_PASSWORD" --read-pai-candidates
```

(If `requests` is already installed, you can drop the `uv run --with requests`
prefix and call `python3 scripts/probe_property.py ...` directly.)

### Tracing an app change to its property

```bash
uv run --with requests python scripts/probe_property.py --country eu --username "YOUR_EMAIL" --password "YOUR_PASSWORD" --trace-app-change
```

1. Run `--trace-app-change`.
2. Wait for the baseline read to finish.
3. Toggle the target setting in the Dreamehome app.
4. Press Enter in the terminal.
5. Check which properties changed.

## Historical / superseded findings

- **Power, pre-resolution:** before the wake command was found, the integration
  could only move the device to standby and not back, which made the Home
  Assistant toggle one-way. A "soft-off" workaround (Sleep Purification at a low
  fan level, which keeps `2/1=1` and stays wakeable) was considered but is no
  longer needed now that real two-way power works.
- **Negative Ion + UVC:** `6/7` was previously labelled "Negative Ion + UVC"
  based on an early trace (`siid=6 piid=7: value 1->0`). That interpretation is
  superseded — `6/7` is Voice Control on the AP10.

## References

- Dreame AP10 app guide: `https://support.dreametech.com/hc/en-us/article_attachments/14128290466319`
- AP10 model page with MiOT spec link: `https://vacuum.mindsolo.net/en/models/dreame.airp.u2507`
- Xiaomi Smart Pet Care Air Purifier MiOT comparison: `https://home.miot-spec.com/spec/xiaomi.airp.cpa5`
- Xiaomi Air Purifier 4 Pro H MiOT comparison: `https://home.miot-spec.com/spec/xiaomi.airp.va4a`
