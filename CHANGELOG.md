# Changelog

All notable changes to this project will be documented in this file.

## [1.1.0] - 2026-03-30

### Fixed

- **Bug:** `departures_count` now correctly reads from options flow override — changing it via reconfigure no longer silently ignored
- **Performance:** Removed redundant API call on sensor setup (`update_before_add=False`) — coordinator already fetches on entry setup
- **CI:** Removed `quality_scale` from manifest (avoids hassfest requiring `quality_scale.yaml` file); added `homeassistant` to CI pip install for more robust test environment
- **Security guards:** Added `isinstance(data, dict)` checks in API response handling; route format validation in coordinator; type safety checks in sensors

---



### Added

- **Expanded test coverage**: Test suite grew from 38 to 71 tests, covering edge cases in sensor state computation, config flow error paths, and coordinator update logic
- **CI quality guards**: Pre-commit hooks and linting rules enforced via GitHub Actions to catch regressions early

### Changed

- **Documentation improvements**: README reorganized with clearer troubleshooting guidance, example automations, and API reference; CHANGELOG kept up to date
- **Code quality improvements**: Consistent code style enforced across the codebase; dead code removed; type annotations improved

## [1.0.0] - 2024-12-19

### Added

- **Real-time SL departures integration** for Home Assistant
  - Fetch live departure data from any Storstockholms Lokaltrafik (SL) stop
  - No API key required; uses open Trafiklab SL Transport API

- **Three sensor types per stop**:
  - **Next Departure**: Displays the next upcoming departure with formatted time (e.g. "Nu", "8 min", "08:42")
  - **Departures**: Shows count of upcoming departures and detailed list with all departure information
  - **Status**: Overall line health status (normal, delayed, cancelled, unknown)

- **Comprehensive departure attributes**:
  - Line number, destination, transport mode
  - Scheduled vs. expected time with delay information
  - Cancellation and delay detection
  - Full departure state details

- **Flexible filtering**:
  - Filter by transport mode (Bus, Metro/Tunnelbana, Commuter Train/Pendeltåg, Tram, Ferry)
  - Filter by specific line numbers (single or multiple routes)
  - Support for direction-specific line filtering

- **Configurable parameters**:
  - Forecast window (how far ahead to fetch departures)
  - Departure count display limit
  - Transport mode and line selection via setup UI

- **Status reporting**:
  - Automatic detection of delays (≥ 2 minutes)
  - Cancellation detection
  - Detailed issues list in status sensor attributes

- **Data updates**: Automatic refresh every 30 seconds
- **Error handling**: Graceful handling of API rate limits, connection errors, and missing data
- **Home Assistant integration**:
  - Config flow for easy setup via UI
  - Device and entity naming per Home Assistant standards
  - Support for automations and templates using sensor states and attributes

### Technical Details

- Built on Home Assistant's DataUpdateCoordinator pattern
- Implements async/await for non-blocking API calls
- Proper error handling with detailed logging
- Tested with Home Assistant validation workflow
