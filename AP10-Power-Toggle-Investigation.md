# AP10 Power Toggle Investigation

Date: 2026-06-07

Device model: `dreame.airp.u2507` / Pet Air Purifier AP10

## RESOLVED (2026-06-07): Working Power-On Command Found

The wake-from-standby command has been identified and verified live on `dreame.airp.u2507` (server `eu`). Real two-way power control now works; the soft-off workaround is no longer required.

| Direction | Command | Verified result |
| --- | --- | --- |
| ON / wake | `action siid=2 aiid=1 in=[{"piid": 1, "value": 1}]` | `2/1` flips `2 -> 1`, mode preserved |
| OFF / standby | `action siid=2 aiid=3` (no input) | `2/1` flips `1 -> 2` |

Notes:

- `aiid=1` is a set-power action that takes the target power as an input property. It only powers ON in practice: `aiid=1` with `value=2` did not move the device to standby, so OFF still uses `aiid=3`.
- The earlier investigation missed this because it tried `aiid=3` with the `{piid:1,value:1}` input and `aiid=1` with no input, but never `aiid=1` with the input value.
- The OFF action `aiid=3` consistently echoes `aiid=9` in its response (`{"siid":2,"aiid":9,"code":0}`); this is cosmetic and OFF still works.
- Two full OFF -> ON round-trips were confirmed reliable.

## Summary (historical, pre-resolution)

The AP10 exposes a readable power state, but the cloud command path previously used by this integration could only reliably move the device into standby. The Dreamehome app could wake the purifier from standby over cloud/mobile internet; the matching cloud command had not yet been identified at the time of writing.

## Confirmed State Mapping

| API | Meaning | Confirmed values |
| --- | --- | --- |
| `siid=2 piid=1` | Power state | `1=on`, `2=standby/off` |
| `siid=2 piid=3` | Mode | Preserved by app OFF/ON |
| `siid=2 piid=4` | Fan level | Preserved by app OFF/ON |

Observed app behavior:

- App OFF changes `2/1` from `1` to `2`.
- App ON changes `2/1` from `2` to `1`.
- App OFF/ON preserves the previous mode and fan level, for example Pet mode `2/3=4`, `2/4=2`, and Custom mode `2/3=3`, `2/4=2`.

## Proven Behavior

- Home Assistant can send a command that switches the purifier OFF into standby.
- Home Assistant cannot currently wake the purifier from standby using the known MIOT-style command paths.
- The Dreamehome app can wake the purifier from standby while the phone has Bluetooth and Wi-Fi disabled and is connected through mobile internet. This proves the app has a cloud-side ON path.
- Device metadata still reports `online=true` while the purifier is in standby, so this is not a fully unreachable offline state.
- `latestStatus` changes from `2` while off to `1` while on, but this has only been confirmed as state metadata, not a control surface.

## Failed Power-On Attempts

The following attempts did not change `siid=2 piid=1` from `2` to `1`:

- Direct `set_properties` for `siid=2 piid=1` with integer `1`.
- Direct `set_properties` for `siid=2 piid=1` with JSON boolean `true`.
- Direct writes both with and without inner per-property `did`.
- MIOT actions:
  - `siid=2 aiid=1`
  - `siid=2 aiid=2`
  - `siid=2 aiid=3`
  - `siid=2 aiid=9`
- `siid=2 aiid=3` with input params:
  - `{"piid": 1, "value": 1}`
  - `{"piid": 1, "value": true}`
- Legacy raw methods:
  - `set_power` with `"on"`, `true`, and `1`
  - `set_prop` with `["power", "on"]`
  - `set_prop` with `["on", true]`
- App-like header variants using:
  - `User-Agent: Dart/3.2 (dart:io)`
  - `Dreame-Auth: bearer <token>`
  - `Dreame-Meta: cv=i_829`

Observed failure patterns:

- Some boolean writes returned timeout-like responses with code `80001`.
- Some integer writes returned a successful service-2 status dump, but did not write the power property.
- `siid=2 aiid=3` can make the device beep, but does not wake it from standby.
- One `siid=2 aiid=3` response reported `aiid=9`, but directly calling `siid=2 aiid=9` timed out and did not wake the purifier.

## Current Conclusion

Real standby OFF is unsafe as Home Assistant's default fan off behavior until the matching cloud ON command is known. Deploying real OFF without real ON makes the HA fan toggle one-way.

Recommended short-term fix:

- Restore wakeable soft-off for HA fan off, using Sleep Purification at fan level 1.
- Keep the real power state read from `siid=2 piid=1` available internally or diagnostically.
- Avoid treating real standby as the default HA fan off path.

Recommended long-term fix:

- Capture the Dreamehome app's successful ON request while the phone is on mobile internet.
- Implement the captured ON command only after verifying that it changes `2/1` from `2` to `1`.
- Preserve app semantics: OFF/ON should keep the stored mode and fan level instead of forcing AI mode.

## Manual Probe Findings (2026-06-07, live device)

Live probing against `dreame.airp.u2507` via `scripts/probe_property.py` on server `eu` confirmed and added the following:

- **Writes are silently no-op'd while in standby.** With the device off (`2/1=2`), writing `siid=2 piid=3` (mode) returned `code 0` / "ok", but the post-write read showed the value unchanged and `2/1` still `2`. The cloud reports success for writes that never reach the device. This is why the current toggle "looks" like it worked but the device never returns.
- **Standby cannot be exited by mode/fan writes.** No property write while in standby changed `2/1` from `2` to `1`. Only the Dreamehome app woke the device.
- **Soft-off never drops the device to standby.** While on (`2/1=1`), writing any mode/fan value kept `2/1=1`. The device stays wakeable. This confirms soft-off is the only HA-controllable two-way path today.
- **Mode writes are reliable two-way while on.** AI↔Sleep↔Custom (`2/3` = 0/2/3) all applied and were confirmed by a follow-up cloud read.
- **Writing a fan level forces Custom mode.** Writing `siid=2 piid=4` switched `2/3` to `3` (Custom). A "Sleep + fan level 1" state is therefore not reachable in one shot; soft-off must be a single mode write.
- **Transient empty reads occur during mode transitions.** One `get_properties` immediately after a write returned no values; a retry a few seconds later succeeded. Control paths should be optimistic and not treat a single empty poll as failure.

Implication: the current real-standby OFF works one-way, exactly as predicted. ON→OFF (to standby) is fully working in HA; OFF→ON (wake) has no known cloud command. The remaining task is to discover the app's wake request.

## Next Investigation Step

The next reliable discovery step is a one-action traffic capture of the Dreamehome app ON request. Further random `aiid` or legacy method probing is not recommended because tested candidates either time out, return status only, or may have unrelated side effects.

Capture plan:

- Put the phone on Wi-Fi and route it through an HTTPS intercepting proxy (for example mitmproxy) on the Mac; install the proxy CA on the phone.
- Confirm the Dreame app traffic to `*.iot.dreame.tech:13267` is decryptable (watch for TLS pinning; if pinned, use a pinning bypass on the app).
- With the device in standby, tap ON once in the app and capture the single request to `/dreame-iot-com*/device/sendCommand` (or any other endpoint hit at that moment).
- Record the exact `method`, `params`, and any unusual headers, then replay it through `scripts/probe_property.py`/`api.py` and verify it flips `2/1` from `2` to `1`.
