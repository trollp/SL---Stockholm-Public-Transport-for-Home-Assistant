# SL — Stockholm Public Transport

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![Validate](https://github.com/trollp/SL---Stockholm-Public-Transport-for-Home-Assistant/actions/workflows/validate.yml/badge.svg)](https://github.com/trollp/SL---Stockholm-Public-Transport-for-Home-Assistant/actions/workflows/validate.yml)

A Home Assistant integration for real-time SL (Storstockholms Lokaltrafik) departures.

**No API key required.** Uses the open Trafiklab SL Transport API.

## Features

- Real-time departure times for any SL stop
- Supports all transport modes: Bus, Metro (Tunnelbana), Commuter Train (Pendeltåg), Tram, Ferry
- Filter by specific line numbers (e.g. only show line 726)
- Delay and cancellation detection
- Three sensor types per stop:
  - **Next Departure** — when is the next bus/train?
  - **Departures** — list of upcoming departures with full details
  - **Status** — overall line status (normal / delayed / cancelled)
- Configurable forecast window and departure count

## How it works

The integration creates three sensors for each SL stop you add:

1. **Next Departure** (`sensor.sl_[stop]_next_departure`)
   - Shows the next upcoming departure as a formatted string (`"Nu"`, `"8 min"`, `"08:42"`)
   - Attributes include full details: line, destination, expected time, delays, cancellations
   - Example: `state: "3 min"` with attributes `line: "726"`, `destination: "Fridhemsplan"`, `delay_minutes: 3`

2. **Departures** (`sensor.sl_[stop]_departures`)
   - State shows the count of upcoming departures within the forecast window
   - Attributes include a `departures` array with all departures and a `next_departure` text string for TTS
   - Example: `state: "3"` (3 departures available) with array of departure details

3. **Status** (`sensor.sl_[stop]_status`)
   - Overall health: `"normal"`, `"delayed"`, `"cancelled"`, or `"unknown"`
   - Attributes include an `issues` list with specific problems (e.g. `"Line 726 08:42 → Fridhemsplan: delayed 3 min"`)
   - Example: `state: "delayed"` when any departure is ≥ 2 min late

**Data updates** every 30 seconds. The integration filters departures by optional transport mode (bus, metro, etc.) and line numbers you select during setup.

## Installation

### Via HACS (recommended)

1. Add this repository as a custom repository in HACS
2. Install "SL — Stockholm Public Transport"
3. Restart Home Assistant
4. Go to Settings → Devices & Services → Add Integration → SL

### Manual

1. Copy `custom_components/sl/` to your HA `custom_components/` directory
2. Restart Home Assistant
3. Add the integration via the UI

## Setup

1. **Search** for your stop by name (e.g. "Ågestavägen", "Odenplan")
2. **Select** the correct stop from the results
3. **Filter** (optional): choose transport mode and/or specific line numbers

## Sensors

For a stop named "Ågestavägen" with line 726 filtered:

| Entity | Example state | Description |
|--------|--------------|-------------|
| `sensor.sl_agestavagen_next_departure` | `3 min` | Next departure display |
| `sensor.sl_agestavagen_departures` | `3` | Number of upcoming departures |
| `sensor.sl_agestavagen_status` | `normal` | Overall status |

### Attributes (next_departure sensor)

```yaml
line: "726"
destination: "Fridhemsplan"
transport_mode: "BUS"
display: "3 min"
scheduled: "07:42"
expected: "07:45"
delay_minutes: 3
is_delayed: true
is_cancelled: false
state: "EXPECTED"
```

### Attributes (departures sensor)

```yaml
next_departure: "3 min → Fridhemsplan (+3 min)"
disrupted: true
departures:
  - line: "726"
    destination: "Fridhemsplan"
    display: "3 min"
    ...
```

### Status values

| Value | Meaning |
|-------|---------|
| `normal` | All departures on time |
| `delayed` | One or more departures delayed ≥ 2 min |
| `cancelled` | One or more departures cancelled |
| `unknown` | No data available |

## Troubleshooting

### No departures showing (state is unknown)
- **Check the stop ID**: Use the search during setup to find the exact stop. Typos or partial names may not find the correct SL stop.
- **Check the forecast window**: Set it to at least 60 minutes during setup. If no departures are scheduled within your window, the sensor will show no data.
- **Check SL API status**: The integration relies on Trafiklab's SL Transport API. If it's down, you'll see `"unknown"` state. Check `https://transport.integration.sl.se`.

### Wrong stop selected
- Re-run the integration config via Settings → Devices & Services → SL → Options.
- Search again for the correct stop name. SL has many stops with similar names.

### Direction filtering not working
- Some lines serve multiple directions at the same stop (e.g., line 726 northbound vs southbound).
- During setup, select the specific direction if offered. If you select **all directions** for a line, departures in all directions will show.
- The integration matches both line number and direction code. If unsure, select "All" to see all departures, then refine later.

### All departures showing as cancelled
- Real SL disruptions can cause widespread cancellations. Check the [SL status page](https://www.sl.se/) or local transit news.
- Verify your stop still has service during your selected forecast hours.

## Example Automations

### Alert when bus is cancelled
```yaml
automation:
  trigger:
    - platform: state
      entity_id: sensor.sl_agestavagen_status
      to: "cancelled"
  action:
    - service: notify.mobile_app_your_phone
      data:
        message: "726 bus cancelled! Check alternatives."
```

### Morning commute announcement
```yaml
automation:
  trigger:
    - platform: time
      at: "07:00:00"
  action:
    - service: tts.speak
      data:
        message: "{{ state_attr('sensor.sl_agestavagen_departures', 'next_departure') }}"
```

## API

This integration uses:
- **Departures**: `https://transport.integration.sl.se/v1/sites/{siteId}/departures`
- **Stop search**: `https://journeyplanner.integration.sl.se/v2/stop-finder`

No API key or Trafiklab account needed.

## License

MIT
