"""The SL (Stockholm Public Transport) integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SLApiClient
from .const import (
    CONF_DEPARTURES_COUNT,
    CONF_FORECAST,
    CONF_ROUTES,
    CONF_SITE_ID,
    CONF_STOP_NAME,
    DOMAIN,
)
from .coordinator import SLDepartureCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SL from a config entry."""
    session = async_get_clientsession(hass)
    client = SLApiClient(session)

    # site_id and stop_name only live in entry.data (set at creation time)
    # forecast/departures_count/routes may be overridden via options flow
    site_id = entry.data[CONF_SITE_ID]
    stop_name = entry.data[CONF_STOP_NAME]
    config = {**entry.data, **entry.options}  # options take precedence

    forecast = config.get(CONF_FORECAST, 60)
    routes = config.get(CONF_ROUTES, [])

    if not routes:
        # Legacy config entry — no routes configured, show all departures
        _LOGGER.warning(
            "SL entry %s (%s) has no routes configured, showing all departures",
            entry.entry_id,
            stop_name,
        )

    coordinator = SLDepartureCoordinator(
        hass=hass,
        client=client,
        site_id=site_id,
        stop_name=stop_name,
        forecast=forecast,
        routes=routes,
    )

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options — reload the entry."""
    await hass.config_entries.async_reload(entry.entry_id)
