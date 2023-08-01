"""Diagnostics support for Moen."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .api import ApiClient
from .const import CLIENT, DOMAIN

CONF_ALTITUDE = "altitude"
CONF_UUID = "uuid"

TO_REDACT = {
    # "address",
    # "full_location",
    # "location",
    # "weather_forecast_location_id",
    # "weather_station_id",
    # "image_url",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    client: ApiClient = hass.data[DOMAIN][entry.entry_id][CLIENT]

    devices = await client.async_get_devices()
    schedules = await client.async_get_schedules(devices["devices"][0]["duid"])

    return async_redact_data({"devices": devices, "schedules": schedules}, TO_REDACT)
