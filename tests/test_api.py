"""Tests for the SL API client."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from custom_components.sl.api import (
    Departure,
    Stop,
    SLApiClient,
    SLApiConnectionError,
    SLApiError,
    _parse_departure,
    _parse_site_id,
    _parse_stop,
    _parse_datetime,
)


class TestParseDatetime:
    def test_valid_datetime(self):
        result = _parse_datetime("2026-03-21T07:42:00")
        assert isinstance(result, datetime)
        assert result.hour == 7
        assert result.minute == 42

    def test_none_returns_none(self):
        assert _parse_datetime(None) is None

    def test_empty_string_returns_none(self):
        assert _parse_datetime("") is None

    def test_with_timezone(self):
        # Should strip timezone offset and parse local portion only
        result = _parse_datetime("2026-03-21T07:42:00+01:00")
        assert result is not None
        assert result.hour == 7


class TestDeparture:
    def _make(self, scheduled="2026-03-21T07:42:00", expected="2026-03-21T07:42:00",
               state="EXPECTED", journey_state="NORMALPROGRESS"):
        return Departure(
            line="726",
            destination="Fridhemsplan",
            transport_mode="BUS",
            scheduled=_parse_datetime(scheduled),
            expected=_parse_datetime(expected),
            display="3 min",
            state=state,
            journey_state=journey_state,
        )

    def test_on_time(self):
        dep = self._make()
        assert dep.is_cancelled is False
        assert dep.is_delayed is False
        assert dep.delay_minutes == 0

    def test_delayed(self):
        dep = self._make(expected="2026-03-21T07:47:00")
        assert dep.is_delayed is True
        assert dep.delay_minutes == 5

    def test_small_delay_not_flagged(self):
        dep = self._make(expected="2026-03-21T07:43:00")
        assert dep.is_delayed is False   # < 2 min threshold
        assert dep.delay_minutes == 1

    def test_cancelled_by_state(self):
        dep = self._make(state="CANCELLED")
        assert dep.is_cancelled is True

    def test_cancelled_by_journey_state(self):
        dep = self._make(journey_state="CANCELLED")
        assert dep.is_cancelled is True

    def test_inhibited_is_cancelled(self):
        dep = self._make(state="INHIBITED")
        assert dep.is_cancelled is True

    def test_as_dict_keys(self):
        dep = self._make()
        d = dep.as_dict()
        assert d["line"] == "726"
        assert d["destination"] == "Fridhemsplan"
        assert d["is_cancelled"] is False
        assert d["delay_minutes"] == 0


class TestParseDeparture:
    def test_valid_departure(self):
        raw = {
            "destination": "Fridhemsplan",
            "display": "3 min",
            "scheduled": "2026-03-21T07:42:00",
            "expected": "2026-03-21T07:42:00",
            "state": "EXPECTED",
            "journey": {"state": "NORMALPROGRESS"},
            "line": {"designation": "726", "transport_mode": "BUS"},
        }
        dep = _parse_departure(raw)
        assert dep is not None
        assert dep.line == "726"
        assert dep.destination == "Fridhemsplan"
        assert dep.transport_mode == "BUS"

    def test_empty_dict_returns_departure_with_defaults(self):
        # _parse_departure is lenient — missing fields default to empty strings
        dep = _parse_departure({})
        assert dep is not None
        assert dep.line == ""

    def test_cancelled_departure(self):
        raw = {
            "destination": "Fridhemsplan",
            "display": "Cancelled",
            "scheduled": "2026-03-21T07:42:00",
            "expected": "2026-03-21T07:42:00",
            "state": "CANCELLED",
            "journey": {"state": "CANCELLED"},
            "line": {"designation": "726", "transport_mode": "BUS"},
        }
        dep = _parse_departure(raw)
        assert dep is not None
        assert dep.is_cancelled is True


class TestParseSiteId:
    def test_standard_prefixed_id(self):
        assert _parse_site_id("18007067") == 7067

    def test_large_prefixed_id(self):
        assert _parse_site_id("18009529") == 9529

    def test_unprefixed_id(self):
        # IDs ≤ 18_000_000 are returned as-is
        assert _parse_site_id("7067") == 7067

    def test_zero(self):
        assert _parse_site_id("0") == 0

    def test_empty(self):
        assert _parse_site_id("") == 0

    def test_non_numeric(self):
        assert _parse_site_id("ABCD") == 0


class TestParseStop:
    def test_valid_bus_stop(self):
        raw = {
            "name": "Test City, Bus Terminal",
            "properties": {"stopId": "18007067"},
            "productClasses": [5],
        }
        stop = _parse_stop(raw)
        assert stop is not None
        assert stop.site_id == 7067
        assert stop.name == "Test City, Bus Terminal"
        assert "BUS" in stop.transport_modes

    def test_metro_stop(self):
        raw = {
            "name": "Test City, Metro Station",
            "properties": {"stopId": "18009117"},
            "productClasses": [0, 5],
        }
        stop = _parse_stop(raw)
        assert stop is not None
        assert "METRO" in stop.transport_modes

    def test_empty_dict_returns_zero_site_id(self):
        # _parse_stop on {} returns site_id=0; the caller filters with `stop.site_id > 0`
        stop = _parse_stop({})
        assert stop is not None
        assert stop.site_id == 0

    def test_invalid_stop_id_returns_zero_site_id(self):
        raw = {
            "name": "Bad Stop",
            "properties": {"stopId": "NOTANUMBER"},
            "productClasses": [],
        }
        stop = _parse_stop(raw)
        assert stop is not None
        assert stop.site_id == 0
