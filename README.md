# Dreame AP-10 Air Purifier for Home Assistant

I have a Dreame AP-10 (the Pet Air Purifier, model `dreame.airp.u2507`) running at home, and Home Assistant had no way to talk to it — Dreame doesn't ship an official air-purifier integration. So I picked apart the cloud API that the Dreamehome app uses and wired it into Home Assistant. This is the result.

Everything runs through Dreame's cloud using your normal Dreamehome login; there's no local API for this device.

## Features

### Fan Entity
- **Power on/off** — turns the purifier on and puts it into standby
- **Mode** — AI Purify, Strong Purification, Sleep Purification, Custom Mode, Pet Purify
- **Fan speed** — 5 speed levels, shown as 20/40/60/80/100% in Home Assistant (setting a speed switches the device to Custom Mode)

### Sensors
- **PM2.5** — real-time particulate reading (µg/m³)
- **Air Quality Level** — numeric air-quality index from the device
- **High Efficiency Composite Filter** — remaining filter percentage
- **High Efficiency Composite Filter Days Left** — remaining filter days
- **High Efficiency Composite Filter Hours Used** — total hours on the current filter
- **Device Location** — the location you set in the Dreamehome app

### Switches
- **Child Lock**
- **Play Mode**
- **Voice Interaction**
- **Keypress Tone** — button-press sounds

### Selects, Number, and Button
- **Light Control** — Off, Blue, Orange, Green
- **Voice Interaction Volume** — Minimum, Moderate, High
- **Timer** — 0–12 hours; `0` disables the timer
- **Filter Reset** — reset the filter lifetime counter

## Installation

### Via HACS (recommended)

1. In Home Assistant: **HACS → Integrations**
2. Click **...** (top right) → **Custom repositories**
3. Paste URL: `https://github.com/Mika255/dreame-ap10-integration`
4. Category: **Integration** → **Add**
5. Search **"Dreame AP-10"** → **Download** → restart HA
6. **Settings → Devices & Services → + Add Integration** → search "Dreame" → enter your Dreamehome credentials

### Manual installation

1. Download or clone this repo
2. Copy `custom_components/dreame_airpurifier/` into your HA `config/custom_components/` directory
3. Restart Home Assistant
4. **Settings → Devices & Services → + Add Integration** → search "Dreame"

## Setup

- Use your **Dreamehome app** credentials (email + password)
- Select your server region (US, EU, CN, etc.)
- The integration discovers every AP-10 on your account automatically
- Multiple purifiers are supported; each shows up as its own device in HA

## Good to know

**Power:** "Turn off" in Home Assistant puts the purifier into standby; "Turn on" wakes it and restores whatever mode and fan level it had before. Power is the one control that doesn't work as a plain property write — the integration drives it through the device's power actions. The details (and how the wake command was found) are in the [API analysis](docs/Dreame-AP10-API-Analysis.md).

**Cloud polling:** the integration polls the Dreame cloud every 30 seconds, so state can lag a little behind physical changes. There's no local API for this device.

## API reference

The full MiOT property/action map, power-control commands, connection details, and the `scripts/probe_property.py` probing tools live in **[docs/Dreame-AP10-API-Analysis.md](docs/Dreame-AP10-API-Analysis.md)**.

## Troubleshooting

- **Login fails?** Make sure the same credentials work in the Dreamehome app — the integration uses the same login.
- **Device unavailable?** Check that it's online in the Dreamehome app and that the region you picked matches your account.
- **Commands not working?** Look under Developer Tools → Logs and search for `dreame_airpurifier`.
- **State not updating?** It polls every 30 seconds; cloud state can lag behind physical changes.

## Thanks

This project builds on [CodyJon's dreame-ap10-integration](https://github.com/CodyJon/dreame-ap10-integration) — the original groundwork for getting the AP-10 into Home Assistant. Thank you for the head start.

## Contributing

Issues, feature requests, and PRs welcome.

## License

MIT License
