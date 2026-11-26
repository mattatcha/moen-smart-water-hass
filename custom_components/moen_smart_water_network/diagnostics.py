"""Diagnostics support for Moen."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data

from .const import CLIENT, DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .coordinator import MoenDataUpdateCoordinator
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
    entry_data = hass.data[DOMAIN][entry.entry_id]
    client: MoenApiClient = entry_data[CLIENT]
    coordinators: list[MoenDataUpdateCoordinator] = entry_data.get("devices", [])

    devices = await client.async_get_devices()
    schedules = await client.async_get_schedules(devices["devices"][0]["duid"])

    coordinator_data: dict[str, Any] = {}
    for coordinator in coordinators:
        coordinator_data[coordinator.id] = {
            # The per-device payload carries add-ons (soil sensors) that the
            # device list omits, plus the live shadow state.
            "device": coordinator.data.get("device") if coordinator.data else None,
            "hydra_overview": coordinator.hydra_overview,
        }

    return async_redact_data(
        {"devices": devices, "schedules": schedules, "coordinators": coordinator_data},
        TO_REDACT,
    )
