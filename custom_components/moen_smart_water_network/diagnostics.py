"""Diagnostics support for Moen."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data

from .const import CLIENT, DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .coordinator import MoenBaseCoordinator
    from .moen_api import MoenApiClient

TO_REDACT = {
    "access_token",
    "refresh_token",
    "id_token",
    "legacyId",
    "federatedIdentity",
    "cognitoIdentityId",
    "email",
    "userId",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    client: MoenApiClient = entry_data[CLIENT]
    devices: list[MoenBaseCoordinator] = entry_data.get("devices", [])

    return async_redact_data(
        {
            # Every device on the account, including unsupported types.
            "devices": await client.async_get_devices(),
            "coordinators": {device.id: device.diagnostics() for device in devices},
        },
        TO_REDACT,
    )
