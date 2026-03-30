"""Sensor platform for SL integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTRIBUTION,
    CONF_DEPARTURES_COUNT,
    CONF_TRANSPORT,
    DOMAIN,
    SENSOR_DEPARTURES,
    SENSOR_NEXT_DEPARTURE,
    SENSOR_STATUS,
    TRANSPORT_ALL,
    TRANSPORT_ICONS,
)
from .coordinator import SLDepartureCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SL sensor entities from a config entry."""
    coordinator: SLDepartureCoordinator = entry.runtime_data
    stop_name = coordinator.stop_name
    transport = entry.data.get(CONF_TRANSPORT, TRANSPORT_ALL)
    departures_count = entry.data.get(CONF_DEPARTURES_COUNT, 3)

    entities = [
        SLNextDepartureSensor(coordinator, entry, stop_name, transport),
        SLDeparturesSensor(coordinator, entry, stop_name, transport, departures_count),
        SLStatusSensor(coordinator, entry, stop_name),
    ]

    async_add_entities(entities, update_before_add=True)


def _get_icon(transport: str) -> str:
    """Return icon for transport mode."""
    return TRANSPORT_ICONS.get(transport, TRANSPORT_ICONS[TRANSPORT_ALL])


class SLBaseSensor(CoordinatorEntity[SLDepartureCoordinator], SensorEntity):
    """Base class for SL sensors."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SLDepartureCoordinator,
        entry: ConfigEntry,
        stop_name: str,
        sensor_type: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._stop_name = stop_name
        self._sensor_type = sensor_type
        self._attr_unique_id = f"{entry.entry_id}_{sensor_type}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(entry.entry_id))},
            name=stop_name,
            manufacturer="Trafiklab / SL",
            model="SL Transport API",
        )


class SLNextDepartureSensor(SLBaseSensor):
    """Sensor showing the next departure time."""

    _attr_translation_key = SENSOR_NEXT_DEPARTURE

    def __init__(
        self,
        coordinator: SLDepartureCoordinator,
        entry: ConfigEntry,
        stop_name: str,
        transport: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, entry, stop_name, SENSOR_NEXT_DEPARTURE)
        self._attr_icon = _get_icon(transport)
        # Not using TIMESTAMP device class — we return a display string like "Nu" / "8 min"

    @property
    def native_value(self) -> str | None:
        """Return the next departure display string (e.g. 'Nu', '8 min', '08:42')."""
        dep = self.coordinator.next_departure
        if dep is None:
            return None
        return dep.display

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        dep = self.coordinator.next_departure
        if dep is None:
            return {}
        return dep.as_dict()


class SLDeparturesSensor(SLBaseSensor):
    """Sensor showing upcoming departures."""

    _attr_translation_key = SENSOR_DEPARTURES

    def __init__(
        self,
        coordinator: SLDepartureCoordinator,
        entry: ConfigEntry,
        stop_name: str,
        transport: str,
        departures_count: int,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, entry, stop_name, SENSOR_DEPARTURES)
        self._attr_icon = _get_icon(transport)
        self._departures_count = departures_count
        self._attr_native_unit_of_measurement = "departures"

    @property
    def native_value(self) -> int:
        """Return number of upcoming departures."""
        if not self.coordinator.data or not isinstance(self.coordinator.data, list):
            return 0
        return len(self.coordinator.data[: self._departures_count])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.coordinator.data if isinstance(self.coordinator.data, list) else []
        shown = data[: self._departures_count]

        # Build a clean summary string for TTS
        dep = self.coordinator.next_departure
        next_str = None
        if dep:
            next_str = f"Line {dep.line} {dep.display} → {dep.destination}"
            if dep.is_delayed:
                next_str += f" (+{dep.delay_minutes} min)"
            if dep.is_cancelled:
                next_str = f"CANCELLED: Line {dep.line} → {dep.destination}"

        # Build per-line next departure map
        per_line_next: dict[str, Any] = {}
        for d in data:
            if d.line not in per_line_next and not d.is_cancelled:
                per_line_next[d.line] = {
                    "display": d.display,
                    "destination": d.destination,
                    "scheduled": d.scheduled_time_str,
                }

        # Build human-readable summary string
        summary_parts = []
        for d in shown:
            if not d.is_cancelled:
                display_str = d.display.replace(" ", "")
                summary_parts.append(f"{d.line} {display_str}→{d.destination}")
            else:
                summary_parts.append(f"{d.line} CANCELLED")
        summary = " | ".join(summary_parts) if summary_parts else "No departures"

        return {
            "next_departure": next_str,
            "departures": [d.as_dict() for d in shown],
            "disrupted": self.coordinator.has_disruptions,
            "per_line_next": per_line_next,
            "summary": summary,
        }


class SLStatusSensor(SLBaseSensor):
    """Sensor showing overall line status."""

    _attr_translation_key = SENSOR_STATUS

    def __init__(
        self,
        coordinator: SLDepartureCoordinator,
        entry: ConfigEntry,
        stop_name: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, entry, stop_name, SENSOR_STATUS)
        self._attr_icon = "mdi:traffic-light"

    @property
    def native_value(self) -> str:
        """Return overall status."""
        return self.coordinator.status

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return issues list."""
        data = self.coordinator.data if isinstance(self.coordinator.data, list) else []
        issues = []
        for dep in data:
            if dep.is_cancelled:
                issues.append(
                    f"Line {dep.line} {dep.scheduled_time_str} → {dep.destination}: CANCELLED"
                )
            elif dep.is_delayed:
                issues.append(
                    f"Line {dep.line} {dep.scheduled_time_str} → {dep.destination}: "
                    f"delayed {dep.delay_minutes} min (now {dep.expected_time_str})"
                )
        return {"issues": issues}
