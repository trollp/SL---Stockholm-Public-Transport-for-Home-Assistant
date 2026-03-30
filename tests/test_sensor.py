"""Tests for SL sensor entities."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock

from custom_components.sl.api import Departure, _parse_datetime
from custom_components.sl.sensor import (
    SLNextDepartureSensor,
    SLDeparturesSensor,
    SLStatusSensor,
)
from custom_components.sl.const import SENSOR_NEXT_DEPARTURE, SENSOR_DEPARTURES, SENSOR_STATUS


def make_dep(
    line, direction_code, destination="Test", transport_mode="BUS",
    state="EXPECTED", journey_state="NORMALPROGRESS", display="3 min"
):
    """Create a Departure for testing."""
    return Departure(
        line=line,
        destination=destination,
        transport_mode=transport_mode,
        scheduled=_parse_datetime("2026-03-21T07:42:00"),
        expected=_parse_datetime("2026-03-21T07:42:00"),
        display=display,
        state=state,
        journey_state=journey_state,
        direction_code=direction_code,
    )


def make_coordinator(data=None):
    """Create a mock coordinator with optional data."""
    coordinator = MagicMock()
    coordinator.data = data
    coordinator.next_departure = None
    coordinator.status = "normal"
    coordinator.has_disruptions = False

    if data:
        # Find next non-cancelled departure
        for dep in data:
            if not dep.is_cancelled:
                coordinator.next_departure = dep
                break

        # Set status
        if data:
            cancelled = [d for d in data if d.is_cancelled]
            delayed = [d for d in data if d.is_delayed and not d.is_cancelled]
            if cancelled:
                coordinator.status = "cancelled"
            elif delayed:
                coordinator.status = "delayed"
            else:
                coordinator.status = "normal"

        # Set has_disruptions
        if data:
            coordinator.has_disruptions = any(d.is_cancelled or d.is_delayed for d in data)

    return coordinator


def make_entry():
    """Create a mock config entry."""
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = {}
    return entry


# ---------------------------------------------------------------------------
# SLNextDepartureSensor tests
# ---------------------------------------------------------------------------

class TestSLNextDepartureSensor:
    def test_native_value_with_departure(self):
        """Test native_value returns display string when departure exists."""
        coordinator = make_coordinator([make_dep("172", 1, display="5 min")])
        entry = make_entry()

        sensor = SLNextDepartureSensor(
            coordinator=coordinator,
            entry=entry,
            stop_name="Test Stop",
            transport="BUS",
        )

        assert sensor.native_value == "5 min"

    def test_native_value_without_departure(self):
        """Test native_value returns None when no departure exists."""
        coordinator = make_coordinator([])
        entry = make_entry()

        sensor = SLNextDepartureSensor(
            coordinator=coordinator,
            entry=entry,
            stop_name="Test Stop",
            transport="BUS",
        )

        assert sensor.native_value is None

    def test_extra_state_attributes_with_departure(self):
        """Test extra_state_attributes includes departure dict."""
        dep = make_dep("172", 1)
        coordinator = make_coordinator([dep])
        entry = make_entry()

        sensor = SLNextDepartureSensor(
            coordinator=coordinator,
            entry=entry,
            stop_name="Test Stop",
            transport="BUS",
        )

        attrs = sensor.extra_state_attributes
        assert attrs is not None
        assert attrs["line"] == "172"
        assert attrs["destination"] == "Test"
        assert attrs["is_cancelled"] is False

    def test_extra_state_attributes_without_departure(self):
        """Test extra_state_attributes returns empty dict when no departure."""
        coordinator = make_coordinator([])
        entry = make_entry()

        sensor = SLNextDepartureSensor(
            coordinator=coordinator,
            entry=entry,
            stop_name="Test Stop",
            transport="BUS",
        )

        attrs = sensor.extra_state_attributes
        assert attrs == {}

    def test_translation_key(self):
        """Test that translation key is set correctly."""
        coordinator = make_coordinator()
        entry = make_entry()

        sensor = SLNextDepartureSensor(
            coordinator=coordinator,
            entry=entry,
            stop_name="Test Stop",
            transport="BUS",
        )

        assert sensor._attr_translation_key == SENSOR_NEXT_DEPARTURE


# ---------------------------------------------------------------------------
# SLDeparturesSensor tests
# ---------------------------------------------------------------------------

class TestSLDeparturesSensor:
    def test_native_value_returns_count(self):
        """Test native_value returns departure count."""
        departures = [make_dep("172", 1), make_dep("172", 2), make_dep("744", 1)]
        coordinator = make_coordinator(departures)
        entry = make_entry()

        sensor = SLDeparturesSensor(
            coordinator=coordinator,
            entry=entry,
            stop_name="Test Stop",
            transport="BUS",
            departures_count=2,
        )

        assert sensor.native_value == 2

    def test_native_value_respects_departures_count(self):
        """Test native_value respects the departures_count limit."""
        departures = [make_dep("172", 1), make_dep("172", 2), make_dep("744", 1)]
        coordinator = make_coordinator(departures)
        entry = make_entry()

        sensor = SLDeparturesSensor(
            coordinator=coordinator,
            entry=entry,
            stop_name="Test Stop",
            transport="BUS",
            departures_count=1,
        )

        assert sensor.native_value == 1

    def test_native_value_zero_when_no_data(self):
        """Test native_value returns 0 when no data."""
        coordinator = make_coordinator(None)
        entry = make_entry()

        sensor = SLDeparturesSensor(
            coordinator=coordinator,
            entry=entry,
            stop_name="Test Stop",
            transport="BUS",
            departures_count=3,
        )

        assert sensor.native_value == 0

    def test_extra_state_attributes_includes_departures(self):
        """Test extra_state_attributes includes departures list."""
        departures = [make_dep("172", 1, "Skarpnäck"), make_dep("172", 2, "Hallunda")]
        coordinator = make_coordinator(departures)
        entry = make_entry()

        sensor = SLDeparturesSensor(
            coordinator=coordinator,
            entry=entry,
            stop_name="Test Stop",
            transport="BUS",
            departures_count=3,
        )

        attrs = sensor.extra_state_attributes
        assert "departures" in attrs
        assert len(attrs["departures"]) == 2
        assert attrs["departures"][0]["line"] == "172"

    def test_extra_state_attributes_includes_summary(self):
        """Test extra_state_attributes includes summary string."""
        departures = [make_dep("172", 1, "Skarpnäck", display="3min")]
        coordinator = make_coordinator(departures)
        entry = make_entry()

        sensor = SLDeparturesSensor(
            coordinator=coordinator,
            entry=entry,
            stop_name="Test Stop",
            transport="BUS",
            departures_count=3,
        )

        attrs = sensor.extra_state_attributes
        assert "summary" in attrs
        assert "172" in attrs["summary"]

    def test_extra_state_attributes_includes_per_line_next(self):
        """Test extra_state_attributes includes per_line_next."""
        departures = [make_dep("172", 1), make_dep("744", 1)]
        coordinator = make_coordinator(departures)
        entry = make_entry()

        sensor = SLDeparturesSensor(
            coordinator=coordinator,
            entry=entry,
            stop_name="Test Stop",
            transport="BUS",
            departures_count=3,
        )

        attrs = sensor.extra_state_attributes
        assert "per_line_next" in attrs
        assert "172" in attrs["per_line_next"]
        assert "744" in attrs["per_line_next"]

    def test_extra_state_attributes_includes_disrupted(self):
        """Test extra_state_attributes includes disrupted flag."""
        departures = [make_dep("172", 1)]
        coordinator = make_coordinator(departures)
        coordinator.has_disruptions = False
        entry = make_entry()

        sensor = SLDeparturesSensor(
            coordinator=coordinator,
            entry=entry,
            stop_name="Test Stop",
            transport="BUS",
            departures_count=3,
        )

        attrs = sensor.extra_state_attributes
        assert "disrupted" in attrs
        assert attrs["disrupted"] is False

    def test_translation_key(self):
        """Test that translation key is set correctly."""
        coordinator = make_coordinator()
        entry = make_entry()

        sensor = SLDeparturesSensor(
            coordinator=coordinator,
            entry=entry,
            stop_name="Test Stop",
            transport="BUS",
            departures_count=3,
        )

        assert sensor._attr_translation_key == SENSOR_DEPARTURES


# ---------------------------------------------------------------------------
# SLStatusSensor tests
# ---------------------------------------------------------------------------

class TestSLStatusSensor:
    def test_native_value_returns_status(self):
        """Test native_value returns coordinator status."""
        coordinator = make_coordinator([make_dep("172", 1)])
        coordinator.status = "normal"
        entry = make_entry()

        sensor = SLStatusSensor(
            coordinator=coordinator,
            entry=entry,
            stop_name="Test Stop",
        )

        assert sensor.native_value == "normal"

    def test_native_value_delayed(self):
        """Test native_value returns 'delayed' status."""
        dep = make_dep("172", 1)
        dep.expected = _parse_datetime("2026-03-21T07:52:00")  # 10 min late
        coordinator = make_coordinator([dep])
        coordinator.status = "delayed"
        entry = make_entry()

        sensor = SLStatusSensor(
            coordinator=coordinator,
            entry=entry,
            stop_name="Test Stop",
        )

        assert sensor.native_value == "delayed"

    def test_native_value_cancelled(self):
        """Test native_value returns 'cancelled' status."""
        coordinator = make_coordinator([make_dep("172", 1, state="CANCELLED")])
        coordinator.status = "cancelled"
        entry = make_entry()

        sensor = SLStatusSensor(
            coordinator=coordinator,
            entry=entry,
            stop_name="Test Stop",
        )

        assert sensor.native_value == "cancelled"

    def test_extra_state_attributes_includes_issues(self):
        """Test extra_state_attributes includes issues list."""
        departures = [
            make_dep("172", 1, state="CANCELLED"),
            make_dep("744", 1),
        ]
        coordinator = make_coordinator(departures)
        entry = make_entry()

        sensor = SLStatusSensor(
            coordinator=coordinator,
            entry=entry,
            stop_name="Test Stop",
        )

        attrs = sensor.extra_state_attributes
        assert "issues" in attrs
        assert isinstance(attrs["issues"], list)

    def test_extra_state_attributes_issues_empty_when_no_disruptions(self):
        """Test extra_state_attributes issues is empty when no disruptions."""
        coordinator = make_coordinator([make_dep("172", 1)])
        entry = make_entry()

        sensor = SLStatusSensor(
            coordinator=coordinator,
            entry=entry,
            stop_name="Test Stop",
        )

        attrs = sensor.extra_state_attributes
        assert "issues" in attrs
        assert len(attrs["issues"]) == 0

    def test_extra_state_attributes_empty_data(self):
        """Test extra_state_attributes when coordinator data is None."""
        coordinator = make_coordinator(None)
        entry = make_entry()

        sensor = SLStatusSensor(
            coordinator=coordinator,
            entry=entry,
            stop_name="Test Stop",
        )

        attrs = sensor.extra_state_attributes
        assert "issues" in attrs
        assert attrs["issues"] == []

    def test_translation_key(self):
        """Test that translation key is set correctly."""
        coordinator = make_coordinator()
        entry = make_entry()

        sensor = SLStatusSensor(
            coordinator=coordinator,
            entry=entry,
            stop_name="Test Stop",
        )

        assert sensor._attr_translation_key == SENSOR_STATUS
