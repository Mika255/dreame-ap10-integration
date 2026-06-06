# Dreame AP10 Missing Controls Analysis

Date: 2026-06-06

Device model: `dreame.airp.u2507`

## Current Result

The Dreame AP10 API-related missing controls are now identified:

| App value / control | API | Type | Result |
| --- | --- | --- | --- |
| High Efficiency Composite Filter percentage | `siid=4/piid=1` | Read-only sensor | Confirmed. Live read returned `80`, matching the app's about 80% remaining. |
| High Efficiency Composite Filter days left | `siid=4/piid=2` | Read-only sensor | Confirmed as remaining filter days. |
| Voice Control | `siid=6/piid=7` | Control | Corrected from the earlier Negative Ion + UVC interpretation. |
| Timer | `siid=6/piid=8` | Number / timer | Confirmed. `0=off`; non-zero values set the timer in hours. |
| Device location | `siid=6/piid=3` | Read-only string | Confirmed. Live read returned `Munich`; this is the user-set device location. |
| LED color | `siid=2/piid=6` | Select-like setting | Confirmed. `-1=off`, `0=blue`, `1=orange`, `2=green`. |
| Voice Control Volume | `siid=2/piid=5` | Number / select-like setting | Confirmed. `80=minimum`, `90=moderate`, `100=high`. |

The previous `siid=6/piid=7` label as "Negative Ion + UVC" was wrong for AP10. It is now identified as Voice Control.

## Confirmed Property Matrix

| Control / candidate | siid | piid / aiid | Type | Status | Comment |
| --- | ---: | ---: | --- | --- | --- |
| Power | 2 | piid 1 | State | Confirmed | `1=on`, `2=standby`; direct writes time out, use action `2/3`. |
| Mode | 2 | piid 3 | Select / fan preset | Confirmed | `1=strong`, `2=sleep purification`, `3=automatic/custom fan mode`, `4=pet`. |
| Fan speed | 2 | piid 4 | Number / fan speed | Confirmed | `1-5`; custom fan speed uses `2/3=3` plus this value. |
| Voice Control Volume | 2 | piid 5 | Number / select-like setting | Confirmed | `80=minimum`, `90=moderate`, `100=high`. |
| LED color | 2 | piid 6 | Select-like setting | Confirmed | `-1=off`, `0=blue`, `1=orange`, `2=green`; current HA "Blue Light" switch is a rough boolean wrapper. |
| Keypress tone | 2 | piid 7 | Toggle | Confirmed | Live probe showed `0=off`, `1=on`. |
| Air quality level | 3 | piid 4 | Read-only sensor | Confirmed | Numeric AQ level. |
| PM2.5 | 3 | piid 5 | Read-only sensor | Confirmed | Particulate reading. |
| Filter life percent | 4 | piid 1 | Read-only sensor | Confirmed | App percentage; live read `80`. |
| Filter days left | 4 | piid 2 | Read-only sensor | Confirmed | Remaining filter days; read-only value. |
| Filter used time | 4 | piid 3 | Read-only sensor | Confirmed in source | Exposed as `Filter Hours Used`. |
| Filter reset | 4 | aiid 1 | Action | Confirmed in source | `reset_filter()` exists, but no HA button is exposed yet. |
| Device location | 6 | piid 3 | Read-only string sensor | Confirmed | Live read `Munich`; user-set app location. |
| Child lock | 6 | piid 5 | Toggle | Confirmed | `0=off`, `1=on`. |
| Play mode | 6 | piid 6 | Toggle | Confirmed | Cat play mode. |
| Voice Control | 6 | piid 7 | Control | Confirmed | Corrected from the earlier Negative Ion + UVC guess. |
| Timer | 6 | piid 8 | Number / timer | Confirmed | `0=off`; non-zero values set the timer in hours. |
| Service-7 candidate / Toggle 4 | 7 | piid 7 | Candidate toggle | Unknown | Keep debug-only until identified. |

## Superseded Negative Ion + UVC Finding

Earlier live trace result:

```text
siid=6 piid=7: code 0->0, value 1->0
```

Updated interpretation:

| Question | Answer |
| --- | --- |
| Is it Negative Ion + UVC? | No. The newer manual mapping corrects `6/7` to Voice Control. |
| Should Home Assistant expose it as one switch? | Not from this evidence alone. Treat `6/7` as Voice Control until values and UX are fully mapped. |
| Is the previous `Negative Ion + UVC` mapping valid? | No. That interpretation is superseded for AP10. |

## Debug Probe Commands

Read the focused PAI values:

```bash
uv run --with requests python scripts/probe_property.py --country eu --username "YOUR_EMAIL" --password "YOUR_PASSWORD" --read-pai-candidates
```

Confirm the Voice Control write path:

```bash
uv run --with requests python scripts/probe_property.py --country eu --username "YOUR_EMAIL" --password "YOUR_PASSWORD" --siid 6 --piid 7 --toggle
```

If another app setting needs mapping, use the app-change tracer:

```bash
uv run --with requests python scripts/probe_property.py --country eu --username "YOUR_EMAIL" --password "YOUR_PASSWORD" --trace-app-change
```

Workflow:

1. Run `--trace-app-change`.
2. Wait for the baseline read to finish.
3. Toggle the target setting in the Dreamehome app.
4. Press Enter in the terminal.
5. Check which properties changed.

## Implementation Notes

Implemented in this branch:

| File | Change |
| --- | --- |
| `custom_components/dreame_airpurifier/api.py` | Added `PROP_DEVICE_LOCATION`; the current implementation may still need the new `6/7` Voice Control and `2/5` Voice Control Volume naming applied. |
| `custom_components/dreame_airpurifier/sensor.py` | Added `Filter Days Left` and `Device Location` sensors. |
| `custom_components/dreame_airpurifier/switch.py` | May still need alignment with the corrected `6/7` Voice Control mapping. |
| `scripts/probe_property.py` | Added focused PAI reads and app-change tracing. |

Still recommended:

| Item | Reason |
| --- | --- |
| Replace Blue Light switch with LED Color select | `2/6` is LED color, not a boolean light; confirmed values are `-1=off`, `0=blue`, `1=orange`, `2=green`. |
| Remove duplicate experimental aliases for `2/6` | Toggle 1 and Toggle 5 duplicate known LED color behavior. |
| Add a button platform for filter reset | `reset_filter()` exists but has no HA entity. |
| Convert timer to number/select | `6/8` is an hour value where `0=off`, not only a 1h toggle. |
| Add Voice Control Volume entity | `2/5` maps to voice volume with known values `80`, `90`, and `100`. |

## External Clues

The Dreame AP10 app guide lists remaining filter life, light color, timer, voice commands, and keypress tone as app features. Comparable MIOT purifier specs label filter `4/2` as filter-left-time and often place anion/UV as adjacent boolean properties on the purifier service. AP10 differs because the newest manual mapping identifies `6/7` as Voice Control and `2/5` as Voice Control Volume.

References:

- Dreame AP10 app guide: `https://support.dreametech.com/hc/en-us/article_attachments/14128290466319`
- AP10 model page with MIOT spec link: `https://vacuum.mindsolo.net/en/models/dreame.airp.u2507`
- Xiaomi Smart Pet Care Air Purifier MIOT comparison: `https://home.miot-spec.com/spec/xiaomi.airp.cpa5`
- Xiaomi Air Purifier 4 Pro H MIOT comparison: `https://home.miot-spec.com/spec/xiaomi.airp.va4a`
