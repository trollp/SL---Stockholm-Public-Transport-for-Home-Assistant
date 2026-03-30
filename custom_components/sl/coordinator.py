"""Data update coordinator for SL integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import Departure, SLApiClient, SLApiConnectionError, SLApiError, SLApiRateLimitError
from .const import DOMAIN, UPDATE_INTERVAL_SECONDS

_LOGGER = logging.getLogger(__name__)


class SLDepartureCoordinator(DataUpdateCoordinator[list[Departure]]):
    """Coordinator to fetch SL departures periodically."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: SLApiClient,
        site_id: int,
        stop_name: str,
        forecast: int,
        routes: list[str] | None = None,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{site_id}",
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
        )
        self.client = client
        self.site_id = site_id
        self.stop_name = stop_name
        self.forecast = forecast
        self.routes = routes or []

    async def _async_update_data(self) -> list[Departure]:
        """Fetch and filter departures from the SL API."""
        try:
            # Always fetch without transport filter — routes handles client-side filtering
            departures = await self.client.get_departures(
                self.site_id, transport=None, forecast=self.forecast
            )
        except SLApiRateLimitError as err:
            _LOGGER.warning(
                "SL API rate limit hit for stop %s (%s) — will retry next interval",
                self.stop_name,
                self.site_id,
            )
            raise UpdateFailed(f"SL API rate limited: {err}") from err
        except SLApiConnectionError as err:
            raise UpdateFailed(f"Cannot connect to SL API: {err}") from err
        except SLApiError as err:
            raise UpdateFailed(f"SL API error: {err}") from err

        if self.routes:
            route_set = set(self.routes)
            # Validate route format: should be "line|direction_code"
            valid_routes = [r for r in self.routes if "|" in r]
            if valid_routes:
                route_set = set(valid_routes)
                # If all selected routes have direction_code 0, fall back to line-only matching
                all_zero_dc = all(r.endswith("|0") for r in valid_routes)
                if all_zero_dc:
                    line_set = {r.split("|")[0] for r in valid_routes}
                    departures = [d for d in departures if d.line in line_set]
                else:
                    departures = [
                        d for d in departures
                        if f"{d.line}|{d.direction_code}" in route_set
                    ]

        return departures

    @property
    def next_departure(self) -> Departure | None:
        """Return the next upcoming (non-cancelled) departure."""
        if not self.data:
            return None
        for dep in self.data:
            if not dep.is_cancelled:
                return dep
        return None

    @property
    def has_disruptions(self) -> bool:
        """Return True if any departures are cancelled or delayed."""
        if not self.data:
            return False
        return any(d.is_cancelled or d.is_delayed for d in self.data)

    @property
    def status(self) -> str:
        """Return overall status string."""
        if not self.data:
            return "unknown"
        cancelled = [d for d in self.data if d.is_cancelled]
        delayed = [d for d in self.data if d.is_delayed and not d.is_cancelled]
        if cancelled:
            return "cancelled"
        if delayed:
            return "delayed"
        return "normal"
