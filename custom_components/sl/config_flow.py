"""Config flow for SL integration."""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

import voluptuous as vol
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SLApiClient, SLApiConnectionError, SLApiError, Stop
from .const import (
    CONF_DEPARTURES_COUNT,
    CONF_FORECAST,
    CONF_ROUTES,
    CONF_SITE_ID,
    CONF_STOP_NAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_SEARCH = "search"
STEP_SELECT = "select"
STEP_ROUTES = "routes"
STEP_OPTIONS = "options"

MODE_ICONS = {
    "BUS": "🚌",
    "TRAIN": "🚆",
    "METRO": "🚇",
    "TRAM": "🚊",
    "SHIP": "⛴️",
}


async def _fetch_route_options(hass, site_id: int) -> list[SelectOptionDict]:
    """Fetch live departures and build route select options grouped by line+direction."""
    session = async_get_clientsession(hass)
    client = SLApiClient(session)
    try:
        departures = await client.get_departures(site_id, transport=None, forecast=90)
    except Exception as exc:  # noqa: BLE001
        _LOGGER.warning("Could not fetch departures for site_id %s: %s", site_id, exc)
        departures = []

    # Group by (transport_mode, line_designation, direction_code) → set of destinations
    groups: dict[tuple[str, str, int], list[str]] = defaultdict(list)
    for dep in departures:
        key = (dep.transport_mode, dep.line, dep.direction_code)
        if dep.destination and dep.destination not in groups[key]:
            groups[key].append(dep.destination)

    options: list[SelectOptionDict] = []
    # Sort by transport_mode, then line (numeric where possible), then direction_code
    def sort_key(k: tuple[str, str, int]) -> tuple[str, int, str, int]:
        mode, line, dc = k
        try:
            line_num = int(line)
        except (ValueError, TypeError):
            line_num = 9999
        return (mode, line_num, line, dc)

    for (mode, line, dc) in sorted(groups.keys(), key=sort_key):
        destinations = groups[(mode, line, dc)]
        dest_examples = " / ".join(destinations[:3])
        icon = MODE_ICONS.get(mode, "🚌")
        label = f"{icon} Line {line} → {dest_examples}"
        value = f"{line}|{dc}"
        options.append(SelectOptionDict(value=value, label=label))

    return options


class SLConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SL."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._stops: list[Stop] = []
        self._selected_stop: Stop | None = None
        self._route_options: list[SelectOptionDict] = []
        self._pending_routes: list[str] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1: Ask user to search for a stop."""
        return await self.async_step_search(user_input)

    async def async_step_search(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Search for a stop by name."""
        errors: dict[str, str] = {}

        if user_input is not None:
            query = user_input.get("query", "").strip()
            if not query:
                errors["query"] = "required"
            else:
                session = async_get_clientsession(self.hass)
                client = SLApiClient(session)
                try:
                    self._stops = await client.find_stops(query)
                except SLApiConnectionError:
                    errors["base"] = "cannot_connect"
                except SLApiError:
                    errors["base"] = "unknown"
                else:
                    if not self._stops:
                        errors["query"] = "no_stops_found"
                    else:
                        return await self.async_step_select()

        return self.async_show_form(
            step_id=STEP_SEARCH,
            data_schema=vol.Schema(
                {vol.Required("query"): vol.All(str, vol.Length(min=2, max=100))}
            ),
            errors=errors,
        )

    async def async_step_select(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2: Let user select from found stops."""
        errors: dict[str, str] = {}

        stop_options = {
            str(stop.site_id): f"{stop.name} (ID: {stop.site_id})"
            for stop in self._stops
        }

        if user_input is not None:
            site_id_str = user_input.get(CONF_SITE_ID, "")
            selected = next(
                (s for s in self._stops if str(s.site_id) == site_id_str), None
            )
            if selected is None:
                errors[CONF_SITE_ID] = "invalid_stop"
            else:
                self._selected_stop = selected
                return await self.async_step_routes()

        return self.async_show_form(
            step_id=STEP_SELECT,
            data_schema=vol.Schema(
                {vol.Required(CONF_SITE_ID): vol.In(stop_options)}
            ),
            errors=errors,
        )

    async def async_step_routes(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 3: Multi-select line+direction combinations to monitor."""
        assert self._selected_stop is not None

        if user_input is not None:
            selected_routes = user_input.get(CONF_ROUTES, [])
            return await self.async_step_options(routes=selected_routes)

        self._route_options = await _fetch_route_options(
            self.hass, self._selected_stop.site_id
        )

        if not self._route_options:
            # No departures found — skip with empty selection
            _LOGGER.info(
                "No departures found for site_id %s, skipping routes step",
                self._selected_stop.site_id,
            )
            return await self.async_step_options(routes=[])

        schema = vol.Schema(
            {
                vol.Optional(CONF_ROUTES, default=[]): SelectSelector(
                    SelectSelectorConfig(
                        options=self._route_options,
                        multiple=True,
                    )
                )
            }
        )
        return self.async_show_form(step_id=STEP_ROUTES, data_schema=schema)

    async def async_step_options(
        self,
        user_input: dict[str, Any] | None = None,
        routes: list[str] | None = None,
    ) -> FlowResult:
        """Step 4: Set count + forecast options."""
        assert self._selected_stop is not None

        # Called from async_step_routes with routes kwarg
        if routes is not None and user_input is None:
            self._pending_routes = routes
            # Show options form
            return self.async_show_form(
                step_id=STEP_OPTIONS,
                data_schema=vol.Schema(
                    {
                        vol.Optional(CONF_DEPARTURES_COUNT, default=3): vol.All(
                            int, vol.Range(min=1, max=10)
                        ),
                        vol.Optional(CONF_FORECAST, default=60): vol.All(
                            int, vol.Range(min=15, max=90)
                        ),
                    }
                ),
            )

        if user_input is not None:
            stop = self._selected_stop
            pending_routes = getattr(self, "_pending_routes", [])
            config_data = {
                CONF_SITE_ID: stop.site_id,
                CONF_STOP_NAME: stop.name,
                CONF_ROUTES: pending_routes,
                CONF_DEPARTURES_COUNT: user_input.get(CONF_DEPARTURES_COUNT, 3),
                CONF_FORECAST: user_input.get(CONF_FORECAST, 60),
            }

            await self.async_set_unique_id(f"sl_{stop.site_id}")
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=stop.name,
                data=config_data,
            )

        # Fallback: show form (shouldn't normally reach here)
        return self.async_show_form(
            step_id=STEP_OPTIONS,
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_DEPARTURES_COUNT, default=3): vol.All(
                        int, vol.Range(min=1, max=10)
                    ),
                    vol.Optional(CONF_FORECAST, default=60): vol.All(
                        int, vol.Range(min=15, max=90)
                    ),
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> SLOptionsFlow:
        """Return the options flow."""
        return SLOptionsFlow(config_entry)


class SLOptionsFlow(OptionsFlow):
    """Handle options for SL."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize."""
        self._config_entry = config_entry
        self._site_id: int = config_entry.data[CONF_SITE_ID]
        self._pending_routes: list[str] = []

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Start options flow — go straight to routes step."""
        return await self.async_step_routes()

    async def async_step_routes(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1 (options): Re-select routes with current selection pre-filled."""
        if user_input is not None:
            self._pending_routes = user_input.get(CONF_ROUTES, [])
            return await self.async_step_options()

        current = {**self._config_entry.data, **self._config_entry.options}
        current_routes: list[str] = current.get(CONF_ROUTES, [])

        route_options = await _fetch_route_options(self.hass, self._site_id)

        if not route_options:
            # No departures — skip routes step, keep existing routes
            self._pending_routes = current_routes
            return await self.async_step_options()

        schema = vol.Schema(
            {
                vol.Optional(CONF_ROUTES, default=current_routes): SelectSelector(
                    SelectSelectorConfig(
                        options=route_options,
                        multiple=True,
                    )
                )
            }
        )
        return self.async_show_form(step_id=STEP_ROUTES, data_schema=schema)

    async def async_step_options(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2 (options): Set count + forecast."""
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    CONF_ROUTES: self._pending_routes,
                    CONF_DEPARTURES_COUNT: user_input.get(CONF_DEPARTURES_COUNT, 3),
                    CONF_FORECAST: user_input.get(CONF_FORECAST, 60),
                },
            )

        current = {**self._config_entry.data, **self._config_entry.options}

        return self.async_show_form(
            step_id=STEP_OPTIONS,
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_DEPARTURES_COUNT,
                        default=current.get(CONF_DEPARTURES_COUNT, 3),
                    ): vol.All(int, vol.Range(min=1, max=10)),
                    vol.Optional(
                        CONF_FORECAST,
                        default=current.get(CONF_FORECAST, 60),
                    ): vol.All(int, vol.Range(min=15, max=90)),
                }
            ),
        )
