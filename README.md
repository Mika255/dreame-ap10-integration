# Dreame AP-10 Air Purifier Integration for Home Assistant

Custom Home Assistant integration for the **Dreame AP-10 Air Purifier** (model `dreame.airp.u2507`), built by reverse-engineering the Dreame Cloud API.

No official Dreame integration exists for air purifiers in Home Assistant.

## Features

### Fan Entity
- **Power on/off** — "Off" uses Sleep Purification at minimum speed to keep the device cloud-connected
- **Mode** — AI Purify, Strong Purification, Sleep Purification, Custom Mode, Pet Purify
- **Fan speed** — 5 speed levels, shown as 20/40/60/80/100% in Home Assistant
- Setting fan speed uses Custom Mode with speed levels 1-5

### Sensors
- **PM2.5** — Real-time particulate matter reading (µg/m³)
- **Air Quality Level** — Numeric air quality index from the device
- **High Efficiency Composite Filter** — Remaining filter percentage
- **High Efficiency Composite Filter Days Left** — Remaining filter days
- **High Efficiency Composite Filter Hours Used** — Total hours on the current filter
- **Device Location** — User-set location from the Dreamehome app

### Switches
- **Child Lock** — Enable or disable the child lock
- **Play Mode** — Enable or disable play mode
- **Voice Interaction** — Enable or disable voice interaction
- **Keypress Tone** — Enable or disable button press sounds

### Selects, Number, and Button
- **Light Control** — Off, Blue, Orange, Green
- **Voice Interaction Volume** — Minimum, Moderate, High
- **Timer** — Set timer duration from 0-12 hours; `0` disables the timer
- **Filter Reset** — Reset the filter lifetime counter

## Installation

### Via HACS (Recommended)

1. In Home Assistant: **HACS -> Integrations**
2. Click **...** (top right) -> **Custom repositories**
3. Paste URL: `https://github.com/CodyJon/dreame-ap10-integration`
4. Category: **Integration** -> **Add**
5. Search **"Dreame AP-10"** -> **Download** -> restart HA
6. **Settings -> Devices & Services -> + Add Integration** -> search "Dreame" -> enter your Dreamehome app credentials

### Manual Installation

1. Download or clone this repo
2. Copy `custom_components/dreame_airpurifier/` into your HA `config/custom_components/` directory
3. Restart Home Assistant
4. **Settings -> Devices & Services -> + Add Integration** -> search "Dreame"

## Setup

- Use your **Dreamehome app** credentials (email + password)
- Select your server region (US, EU, CN, etc.)
- The integration automatically discovers all AP-10 purifiers on your account
- Multiple purifiers are supported; each appears as a separate device in HA

## Important Notes

### Power Behavior

The AP-10 enters a deep standby when powered off that disconnects it from the cloud entirely. Neither the Dreamehome app nor this integration can wake it remotely. To keep the device controllable:

- **"Turn off" in HA** switches to Sleep Purification at the lowest fan speed
- **"Turn on" in HA** switches back to AI Purify
- Avoid using the physical power button to turn it off if you want remote control to keep working

### Cloud Polling

This integration communicates via the Dreame Cloud API, the same cloud path used by the Dreamehome app. It polls for state updates every 30 seconds. Commands are sent through the cloud; there is no local API available for this device.

## Verified Property Map

| siid | piid / aiid | Property | Values |
|------|-------------|----------|--------|
| 2 | piid 1 | Power | `1=on`, `2=standby` |
| 2 | piid 3 | Mode | `0=AI Purify`, `1=Strong Purification`, `2=Sleep Purification`, `3=Custom Mode`, `4=Pet Purify` |
| 2 | piid 4 | Fan Speed | `1-5`; used with `2/3=3` for Custom Mode |
| 2 | piid 5 | Voice Interaction Volume | `80=minimum`, `90=moderate`, `100=high` |
| 2 | piid 6 | Light Control | `-1=off`, `0=blue`, `1=orange`, `2=green` |
| 2 | piid 7 | Keypress Tone | `0=off`, `1=on` |
| 3 | piid 4 | Air Quality Level | Numeric index |
| 3 | piid 5 | PM2.5 | µg/m³ |
| 4 | piid 1 | High Efficiency Composite Filter | `0-100%` remaining |
| 4 | piid 2 | High Efficiency Composite Filter Days Left | Remaining days |
| 4 | piid 3 | High Efficiency Composite Filter Used | Hours |
| 4 | aiid 1 | High Efficiency Composite Filter Reset | Action |
| 6 | piid 3 | Device Location | User-set location string |
| 6 | piid 5 | Child Lock | `0=off`, `1=on` |
| 6 | piid 6 | Play Mode | `0=off`, `1=on` |
| 6 | piid 7 | Voice Interaction | `0=off`, `1=on` |
| 6 | piid 8 | Timer | `0=off`, `1-12` hours |

Power control requires action `siid=2, aiid=3`; direct writes to `siid=2, piid=1` time out. Mode and fan speed can be set via `set_properties` on `siid=2`. For Custom Mode fan speed, set `siid=2, piid=3` to `3` and `siid=2, piid=4` to speed `1-5`.

## Property Probing

The included probe script can read or write raw properties, scan property ranges, and trace app changes:

```bash
python3 scripts/probe_property.py --country eu --username "YOUR_EMAIL" --password "YOUR_PASSWORD" --siid 6 --piid 8
python3 scripts/probe_property.py --country eu --username "YOUR_EMAIL" --password "YOUR_PASSWORD" --siid 6 --piid 8 --value 2
python3 scripts/probe_property.py --country eu --username "YOUR_EMAIL" --password "YOUR_PASSWORD" --scan-siids 2-8 --scan-piids 1-12
python3 scripts/probe_property.py --country eu --username "YOUR_EMAIL" --password "YOUR_PASSWORD" --trace-app-change

# No local requests install? Use uv instead:
uv run --with requests python3 scripts/probe_property.py --country eu --username "YOUR_EMAIL" --password "YOUR_PASSWORD" --siid 6 --piid 8
uv run --with requests python3 scripts/probe_property.py --country eu --username "YOUR_EMAIL" --password "YOUR_PASSWORD" --siid 6 --piid 8 --value 2
uv run --with requests python3 scripts/probe_property.py --country eu --username "YOUR_EMAIL" --password "YOUR_PASSWORD" --scan-siids 2-8 --scan-piids 1-12
uv run --with requests python3 scripts/probe_property.py --country eu --username "YOUR_EMAIL" --password "YOUR_PASSWORD" --trace-app-change
```

## Troubleshooting

- **Login fails?** Verify your credentials work in the Dreamehome app. The integration uses the same login.
- **Device unavailable?** Make sure the purifier is powered on, not in deep standby. Check that it shows online in the Dreamehome app.
- **Commands not working?** Check HA logs under Developer Tools -> Logs, search for `dreame_airpurifier`.
- **State not updating?** The integration polls every 30 seconds. Cloud state can sometimes lag behind physical changes.

## Contributing

Issues, feature requests, and PRs welcome.

## License

MIT License
