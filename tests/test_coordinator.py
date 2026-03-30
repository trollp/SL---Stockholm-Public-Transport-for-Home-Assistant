"""Tests for SLDepartureCoordinator route filtering and properties."""
import sys
import os
import asyncio
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import AsyncMock, MagicMock

from custom_components.sl.api import (
    Departure,
    SLApiConnectionError,
    SLApiRateLimitError,
    _parse_datetime,
)
from custom_components.sl.coordinator import SLDepartureCoordinator
from homeassistant.helpers.update_coordinator import UpdateFailed


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_dep(line, direction_code, destination="Test", transport_mode="BUS",
             state="EXPECTED", journey_state="NORMALPROGRESS"):
    return Departure(
        line=line,
        destination=destination,
        transport_mode=transport_mode,
        scheduled=_parse_datetime("2026-03-21T07:42:00"),
        expected=_parse_datetime("2026-03-21T07:42:00"),
        display="3 min",
        state=state,
        journey_state=journey_state,
        direction_code=direction_code,
    )


def make_coordinator(routes=None, departures=None):
    """Return a coordinator with a mocked async client."""
    hass = MagicMock()
    client = MagicMock()
    client.get_departures = AsyncMock(return_value=departures or [])
    coord = SLDepartureCoordinator(
        hass=hass,
        client=client,
        site_id=7067,
        stop_name="Test Stop",
        forecast=60,
        routes=routes or [],
    )
    return coord, client


def apply_filter(coord, departures):
    """Run the same filtering logic as _async_update_data without calling the API."""
    if not coord.routes:
        return departures[:]
    route_set = set(coord.routes)
    all_zero_dc = all(r.endswith("|0") for r in coord.routes)
    if all_zero_dc:
        line_set = {r.split("|")[0] for r in coord.routes}
        return [d for d in departures if d.line in line_set]
    return [d for d in departures if f"{d.line}|{d.direction_code}" in route_set]


# ---------------------------------------------------------------------------
# Route filtering
# ---------------------------------------------------------------------------

class TestCoordinatorRoutesFilter:
    def test_no_routes_shows_all(self):
        departures = [make_dep("172", 1), make_dep("172", 2), make_dep("744", 1)]
        coord, _ = make_coordinator(routes=[])
        result = apply_filter(coord, departures)
        assert len(result) == 3

    def test_filter_by_line_and_direction(self):
        departures = [
            make_dep("172", 1, "Skarpnäck"),
            make_dep("172", 2, "Hallunda"),
            make_dep("744", 1, "Högdalen"),
        ]
        coord, _ = make_coordinator(routes=["172|1"])
        result = apply_filter(coord, departures)
        assert len(result) == 1
        assert result[0].destination == "Skarpnäck"

    def test_multiple_routes(self):
        departures = [
            make_dep("172", 1, "Skarpnäck"),
            make_dep("172", 2, "Hallunda"),
            make_dep("744", 1, "Högdalen"),
            make_dep("744", 2, "Gladö kvarn"),
        ]
        coord, _ = make_coordinator(routes=["172|1", "744|2"])
        result = apply_filter(coord, departures)
        assert len(result) == 2
        destinations = {d.destination for d in result}
        assert "Skarpnäck" in destinations
        assert "Gladö kvarn" in destinations

    def test_zero_direction_code_falls_back_to_line_only(self):
        departures = [
            make_dep("172", 0, "Skarpnäck"),
            make_dep("172", 0, "Hallunda"),
            make_dep("744", 0, "Högdalen"),
        ]
        coord, _ = make_coordinator(routes=["172|0"])
        result = apply_filter(coord, departures)
        assert len(result) == 2
        assert all(d.line == "172" for d in result)

    def test_excludes_non_matching(self):
        departures = [make_dep("172", 1, "Skarpnäck"), make_dep("999", 1, "Unknown")]
        coord, _ = make_coordinator(routes=["172|1"])
        result = apply_filter(coord, departures)
        assert len(result) == 1
        assert result[0].line == "172"


# ---------------------------------------------------------------------------
# Coordinator properties (.next_departure, .status, .has_disruptions)
# ---------------------------------------------------------------------------

class TestCoordinatorProperties:
    def _coord(self, data):
        coord, _ = make_coordinator()
        coord.data = data
        return coord

    def test_next_departure_skips_cancelled(self):
        coord = self._coord([
            make_dep("172", 1, state="CANCELLED"),
            make_dep("172", 1, "Next one"),
        ])
        nd = coord.next_departure
        assert nd is not None
        assert nd.destination == "Next one"

    def test_next_departure_none_when_empty(self):
        coord = self._coord([])
        assert coord.next_departure is None

    def test_next_departure_none_when_data_is_none(self):
        coord = self._coord(None)
        assert coord.next_departure is None

    def test_status_normal(self):
        coord = self._coord([make_dep("172", 1)])
        assert coord.status == "normal"

    def test_status_delayed(self):
        dep = make_dep("172", 1)
        dep.expected = _parse_datetime("2026-03-21T07:52:00")  # 10 min late
        coord = self._coord([dep])
        assert coord.status == "delayed"

    def test_status_cancelled(self):
        coord = self._coord([make_dep("172", 1, state="CANCELLED")])
        assert coord.status == "cancelled"

    def test_status_unknown_when_no_data(self):
        coord = self._coord(None)
        assert coord.status == "unknown"

    def test_has_disruptions_false_when_normal(self):
        coord = self._coord([make_dep("172", 1)])
        assert coord.has_disruptions is False

    def test_has_disruptions_true_when_cancelled(self):
        coord = self._coord([make_dep("172", 1, state="CANCELLED")])
        assert coord.has_disruptions is True


# ---------------------------------------------------------------------------
# Coordinator _async_update_data() tests
# ---------------------------------------------------------------------------

class TestCoordinatorAsyncUpdateData:
    def test_filtering_applied(self):
        """Test that route filtering is applied to departures."""
        async def run_test():
            hass = MagicMock()
            client = MagicMock()
            departures = [
                make_dep("172", 1, "Skarpnäck"),
                make_dep("172", 2, "Hallunda"),
                make_dep("744", 1, "Högdalen"),
            ]
            client.get_departures = AsyncMock(return_value=departures)

            coord = SLDepartureCoordinator(
                hass=hass,
                client=client,
                site_id=7067,
                stop_name="Test Stop",
                forecast=60,
                routes=["172|1"],
            )

            result = await coord._async_update_data()
            assert len(result) == 1
            assert result[0].destination == "Skarpnäck"

        asyncio.run(run_test())

    def test_connection_error_raises_update_failed(self):
        """Test that connection error is converted to UpdateFailed."""
        async def run_test():
            hass = MagicMock()
            client = MagicMock()
            client.get_departures = AsyncMock(
                side_effect=SLApiConnectionError("Cannot connect")
            )

            coord = SLDepartureCoordinator(
                hass=hass,
                client=client,
                site_id=7067,
                stop_name="Test Stop",
                forecast=60,
            )

            with pytest.raises(UpdateFailed, match="Cannot connect to SL API"):
                await coord._async_update_data()

        asyncio.run(run_test())

    def test_rate_limit_error_raises_update_failed(self):
        """Test that rate limit error is converted to UpdateFailed."""
        async def run_test():
            hass = MagicMock()
            client = MagicMock()
            client.get_departures = AsyncMock(
                side_effect=SLApiRateLimitError("Rate limited")
            )

            coord = SLDepartureCoordinator(
                hass=hass,
                client=client,
                site_id=7067,
                stop_name="Test Stop",
                forecast=60,
            )

            with pytest.raises(UpdateFailed, match="SL API rate limited"):
                await coord._async_update_data()

        asyncio.run(run_test())

    def test_no_routes_returns_all_departures(self):
        """Test that without routes, all departures are returned."""
        async def run_test():
            hass = MagicMock()
            client = MagicMock()
            departures = [
                make_dep("172", 1),
                make_dep("172", 2),
                make_dep("744", 1),
            ]
            client.get_departures = AsyncMock(return_value=departures)

            coord = SLDepartureCoordinator(
                hass=hass,
                client=client,
                site_id=7067,
                stop_name="Test Stop",
                forecast=60,
                routes=[],
            )

            result = await coord._async_update_data()
            assert len(result) == 3

        asyncio.run(run_test())
