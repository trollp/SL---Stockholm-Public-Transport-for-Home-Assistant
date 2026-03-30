"""SL Transport API client."""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import aiohttp

from .const import (
    API_BASE,
    CANCELLED_DEP_STATES,
    CANCELLED_JOURNEY_STATES,
    DELAY_THRESHOLD_MINUTES,
    MAX_RESPONSE_BYTES,
    STOP_FINDER_BASE,
    TRANSPORT_ALL,
)

_LOGGER = logging.getLogger(__name__)

TIMEOUT = aiohttp.ClientTimeout(total=10)


class SLApiError(Exception):
    """General SL API error."""


class SLApiConnectionError(SLApiError):
    """SL API connection error."""


class SLApiRateLimitError(SLApiError):
    """SL API rate limit error (429)."""


@dataclass
class Departure:
    """Represents a single departure."""

    line: str
    destination: str
    transport_mode: str
    scheduled: datetime | None
    expected: datetime | None
    display: str
    state: str
    journey_state: str
    direction_code: int = 0
    direction: str = ""

    @property
    def is_cancelled(self) -> bool:
        """Return True if the departure is cancelled."""
        return (
            self.state in CANCELLED_DEP_STATES
            or self.journey_state in CANCELLED_JOURNEY_STATES
        )

    @property
    def delay_minutes(self) -> int:
        """Return delay in minutes (0 if on time or unknown)."""
        if self.scheduled is None or self.expected is None:
            return 0
        delta = self.expected - self.scheduled
        return max(0, int(delta.total_seconds() / 60))

    @property
    def is_delayed(self) -> bool:
        """Return True if delayed by more than the threshold."""
        return self.delay_minutes >= DELAY_THRESHOLD_MINUTES

    @property
    def expected_time_str(self) -> str | None:
        """Return expected time as HH:MM string."""
        if self.expected is None:
            return None
        return self.expected.strftime("%H:%M")

    @property
    def scheduled_time_str(self) -> str | None:
        """Return scheduled time as HH:MM string."""
        if self.scheduled is None:
            return None
        return self.scheduled.strftime("%H:%M")

    def as_dict(self) -> dict[str, Any]:
        """Return as dict for HA attributes."""
        return {
            "line": self.line,
            "destination": self.destination,
            "transport_mode": self.transport_mode,
            "display": self.display,
            "scheduled": self.scheduled_time_str,
            "expected": self.expected_time_str,
            "delay_minutes": self.delay_minutes,
            "is_delayed": self.is_delayed,
            "is_cancelled": self.is_cancelled,
            "state": self.state,
            "direction_code": self.direction_code,
            "direction": self.direction,
        }


@dataclass
class Stop:
    """Represents a transit stop."""

    site_id: int
    name: str
    transport_modes: list[str]

    def __str__(self) -> str:
        modes = ", ".join(self.transport_modes) if self.transport_modes else "unknown"
        return f"{self.name} (ID: {self.site_id}, modes: {modes})"


def _parse_datetime(value: str | None) -> datetime | None:
    """Parse ISO datetime string to datetime object."""
    if not value:
        return None
    try:
        # Remove timezone info for simplicity — SL API returns local time
        clean = value[:19]
        return datetime.fromisoformat(clean)
    except (ValueError, TypeError):
        return None


def _parse_site_id(stop_id_str: str) -> int:
    """Parse a Journey Planner stopId string to a numeric site_id.

    The API returns IDs like "18007067" where "1800" is a regional prefix.
    We strip the known prefix to get the actual site_id used by the departures API.
    Falls back to parsing the full string as an integer if no prefix is found.
    """
    if not stop_id_str:
        return 0
    try:
        numeric = int(stop_id_str)
    except (ValueError, TypeError):
        return 0

    # Strip the "1800" Stockholm region prefix if present (IDs > 18000000)
    if numeric > 18_000_000:
        return numeric - 18_000_000
    return numeric


def _parse_departure(raw: dict[str, Any]) -> Departure | None:
    """Parse a raw departure dict from the API."""
    try:
        line_info = raw.get("line", {})
        journey_info = raw.get("journey", {})

        return Departure(
            line=str(line_info.get("designation", "")),
            destination=str(raw.get("destination", "")),
            transport_mode=str(line_info.get("transport_mode", "UNKNOWN")),
            scheduled=_parse_datetime(raw.get("scheduled")),
            expected=_parse_datetime(raw.get("expected")),
            display=str(raw.get("display", "")),
            state=str(raw.get("state", "")),
            journey_state=str(journey_info.get("state", "")),
            direction_code=int(raw.get("direction_code", 0)),
            direction=str(raw.get("direction", "")),
        )
    except Exception as exc:  # noqa: BLE001
        _LOGGER.warning("Failed to parse departure entry: %s", exc)
        return None


def _parse_stop(raw: dict[str, Any]) -> Stop | None:
    """Parse a raw stop dict from the stop-finder API."""
    try:
        stop_id_str = raw.get("properties", {}).get("stopId", "")
        site_id = _parse_site_id(str(stop_id_str))

        product_classes = raw.get("productClasses", [])
        mode_map = {0: "METRO", 1: "METRO", 2: "TRAIN", 5: "BUS", 7: "TRAM", 10: "SHIP"}
        modes = list({mode_map[p] for p in product_classes if p in mode_map})

        return Stop(
            site_id=site_id,
            name=str(raw.get("name", "")),
            transport_modes=modes,
        )
    except Exception as exc:  # noqa: BLE001
        _LOGGER.warning("Failed to parse stop entry: %s", exc)
        return None


async def _read_json(resp: aiohttp.ClientResponse) -> Any:
    """Read response body with a size cap, then parse as JSON.

    Prevents memory exhaustion if the remote server returns an unexpectedly
    large payload (e.g. due to misconfiguration or a compromised endpoint).
    """
    raw = await resp.content.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise SLApiError(
            f"Response from SL API exceeded size limit ({MAX_RESPONSE_BYTES} bytes)"
        )
    return json.loads(raw)


class SLApiClient:
    """Async client for the SL Transport API."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize the client."""
        self._session = session

    async def get_departures(
        self,
        site_id: int,
        transport: str | None = None,
        forecast: int = 60,
    ) -> list[Departure]:
        """Fetch departures for a site."""
        url = f"{API_BASE}/sites/{site_id}/departures"
        params: dict[str, Any] = {"forecast": forecast}
        if transport and transport != TRANSPORT_ALL:
            params["transport"] = transport

        try:
            async with self._session.get(url, params=params, timeout=TIMEOUT) as resp:
                if resp.status == 429:
                    raise SLApiRateLimitError("Rate limited by SL API")
                if resp.status != 200:
                    raise SLApiError(f"SL API returned status {resp.status}")
                data = await _read_json(resp)
        except SLApiError:
            raise
        except aiohttp.ClientConnectionError as err:
            raise SLApiConnectionError(f"Cannot connect to SL API: {err}") from err
        except asyncio.TimeoutError as err:
            raise SLApiConnectionError("SL API request timed out") from err
        except (json.JSONDecodeError, ValueError) as err:
            raise SLApiError(f"SL API returned invalid JSON: {err}") from err

        departures = []
        if isinstance(data, dict):
            for raw in data.get("departures", []):
                dep = _parse_departure(raw)
                if dep is not None:
                    departures.append(dep)

        return departures

    async def find_stops(self, query: str) -> list[Stop]:
        """Search for stops by name."""
        url = f"{STOP_FINDER_BASE}/stop-finder"
        params = {
            "name_sf": query,
            "type_sf": "any",
            "any_obj_filter_sf": 2,
        }

        try:
            async with self._session.get(url, params=params, timeout=TIMEOUT) as resp:
                if resp.status != 200:
                    raise SLApiError(f"Stop finder returned status {resp.status}")
                data = await _read_json(resp)
        except SLApiError:
            raise
        except aiohttp.ClientConnectionError as err:
            raise SLApiConnectionError(f"Cannot connect to stop finder: {err}") from err
        except asyncio.TimeoutError as err:
            raise SLApiConnectionError("Stop finder request timed out") from err
        except (json.JSONDecodeError, ValueError) as err:
            raise SLApiError(f"Stop finder returned invalid JSON: {err}") from err

        stops = []
        if isinstance(data, dict):
            for raw in data.get("locations", []):
                stop = _parse_stop(raw)
                if stop is not None and stop.site_id > 0:
                    stops.append(stop)

        # Deduplicate by site_id
        seen: set[int] = set()
        unique = []
        for stop in stops:
            if stop.site_id not in seen:
                seen.add(stop.site_id)
                unique.append(stop)

        return unique
