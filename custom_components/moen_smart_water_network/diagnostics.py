"""Diagnostics support for Moen."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data

from .const import CLIENT, DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .moen_api import MoenApiClient

TO_REDACT = {
    "access_token",
    "refresh_token",
    "id_token",
    "legacyId",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    client: MoenApiClient = hass.data[DOMAIN][entry.entry_id][CLIENT]

    devices = await client.async_get_devices()
    schedules = await client.async_get_schedules(devices["devices"][0]["duid"])

    return async_redact_data({"devices": devices, "schedules": schedules}, TO_REDACT)
