"""
Custom integration to integrate moen_smart_water_network with Home Assistant.

For more details about this integration, please refer to
https://github.com/mattatcha/moen-smart-water-hass
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.exceptions import (
    ConfigEntryNotReady,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import ApiClient, ApiClientError
from .const import CLIENT, CONF_REFRESH_TOKEN, DOMAIN
from .coordinator import MoenDataUpdateCoordinator

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant, ServiceCall

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up this integration using UI."""
    session = async_get_clientsession(hass)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {}
    try:
        hass.data[DOMAIN][entry.entry_id][CLIENT] = client = ApiClient(
            access_token=entry.data[CONF_ACCESS_TOKEN],
            refresh_token=entry.data[CONF_REFRESH_TOKEN],
            session=session,
        )
    except ApiClientError as err:
        raise ConfigEntryNotReady from err

    resp = await client.async_get_devices()
    _LOGGER.debug("INITIAL devices: %s", resp)

    hass.data[DOMAIN][entry.entry_id]["devices"] = devices = [
        MoenDataUpdateCoordinator(hass, client, device["duid"], device)
        for device in resp["devices"]
    ]


    tasks = [device.async_config_entry_first_refresh() for device in devices]
    await asyncio.gather(*tasks)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register service
    async def start_watering_service(call: ServiceCall) -> None:
        """Handle start watering service call."""
        device_id = call.data.get("device_id")
        zone_id = f"{device_id}_{call.data.get('zone_id')}"
        duration = call.data.get("duration", 5)  # Default 5 minutes

        # Find the client for the device
        client = None
        for entry_data in hass.data[DOMAIN].values():
            if isinstance(entry_data, dict) and CLIENT in entry_data:
                client = entry_data[CLIENT]
                break

        if not client:
            raise ServiceValidationError("No Moen client found")

        try:
            # Create zones dict for manual run - zone_id maps to duration in minutes
            zones = [{"id": zone_id, "duration": duration}]
            await client.async_manual_run(
                device_id=device_id, name="Home Assistant Manual Run", zones=zones
            )
        except Exception as err:
            msg = f"Failed to start watering: {err}"
            raise HomeAssistantError(msg) from err

    hass.services.async_register(
        DOMAIN,
        "start_watering",
        start_watering_service,
        schema=vol.Schema(
            {
                vol.Required("device_id"): cv.string,
                vol.Required("zone_id"): cv.string,
                vol.Optional("duration", default=5): cv.positive_int,
            }
        ),
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
