"""Constants for the SL integration."""

DOMAIN = "sl"
ATTRIBUTION = "Data provided by Trafiklab / SL Transport API"

# API
API_BASE = "https://transport.integration.sl.se/v1"
STOP_FINDER_BASE = "https://journeyplanner.integration.sl.se/v2"
DEFAULT_FORECAST = 60
DEFAULT_DEPARTURES_COUNT = 3
UPDATE_INTERVAL_SECONDS = 30
MAX_RESPONSE_BYTES = 524_288   # 512 KB — guard against oversized API responses
STOP_ID_PREFIX = "1800"        # Journey planner stopId prefix for Stockholm region

# Transport modes
TRANSPORT_ALL = "ALL"
TRANSPORT_BUS = "BUS"
TRANSPORT_METRO = "METRO"
TRANSPORT_TRAIN = "TRAIN"
TRANSPORT_TRAM = "TRAM"
TRANSPORT_SHIP = "SHIP"

TRANSPORT_MODES = {
    TRANSPORT_ALL: "All modes",
    TRANSPORT_BUS: "Bus",
    TRANSPORT_METRO: "Metro",
    TRANSPORT_TRAIN: "Train (Pendeltåg)",
    TRANSPORT_TRAM: "Tram",
    TRANSPORT_SHIP: "Ship / Ferry",
}

TRANSPORT_ICONS = {
    TRANSPORT_BUS: "mdi:bus",
    TRANSPORT_METRO: "mdi:subway",
    TRANSPORT_TRAIN: "mdi:train",
    TRANSPORT_TRAM: "mdi:tram",
    TRANSPORT_SHIP: "mdi:ferry",
    TRANSPORT_ALL: "mdi:transit-connection-variant",
}

# Journey states that indicate problems
CANCELLED_JOURNEY_STATES = {"CANCELLED", "INHIBITED"}
CANCELLED_DEP_STATES = {"CANCELLED", "INHIBITED", "NOTEXPECTED"}

# Delay threshold in minutes
DELAY_THRESHOLD_MINUTES = 2

# Config flow keys
CONF_SITE_ID = "site_id"
CONF_STOP_NAME = "stop_name"
CONF_TRANSPORT = "transport"       # kept for backward compat (legacy entries)
CONF_LINES = "lines"               # kept for backward compat (legacy entries)
CONF_DEPARTURES_COUNT = "departures_count"
CONF_FORECAST = "forecast"
CONF_DIRECTION_CODE = "direction_code"  # kept for backward compat (legacy entries)
CONF_ROUTES = "routes"             # new: list of "line|direction_code" strings

# Sensor types
SENSOR_NEXT_DEPARTURE = "next_departure"
SENSOR_DEPARTURES = "departures"
SENSOR_STATUS = "status"
