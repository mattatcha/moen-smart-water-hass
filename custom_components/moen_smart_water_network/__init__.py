"""
Custom integration to integrate moen_smart_water_network with Home Assistant.

For more details about this integration, please refer to
https://github.com/mattatcha/moen-smart-water-hass
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CLIENT, CONF_REFRESH_TOKEN, DOMAIN
from .coordinator import COORDINATOR_TYPES, MoenBaseCoordinator
from .moen_api import (
    MoenApiAuthenticationError,
    MoenApiClient,
    MoenApiError,
    MoenAuth,
    MoenMqttClient,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant, ServiceCall
    from homeassistant.helpers.device_registry import DeviceEntry
    from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

MQTT_TASK = "mqtt_task"

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CALENDAR,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
    Platform.VALVE,
]

START_WATERING_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): cv.string,
        vol.Required("zone_id"): cv.string,
        vol.Optional("duration", default=5): cv.positive_int,
    }
)


async def async_setup(hass: HomeAssistant, _config: ConfigType) -> bool:
    """Set up the Moen Smart Water Network integration."""
    hass.data.setdefault(DOMAIN, {})

    async def start_watering_service(call: ServiceCall) -> None:
        """Handle start watering service call."""
        device_id = call.data.get("device_id")
        zone_id = f"{device_id}_{call.data.get('zone_id')}"
        duration = call.data.get("duration", 5)

        svc_client = None
        for entry_data in hass.data[DOMAIN].values():
            if isinstance(entry_data, dict) and CLIENT in entry_data:
                svc_client = entry_data[CLIENT]
                break

        if not svc_client:
            raise ServiceValidationError("No Moen client found")

        try:
            zones = [{"id": zone_id, "duration": duration}]
            await svc_client.async_create_irrigation_manual_plan(
                device_id=device_id, name="Home Assistant Manual Run", zones=zones
            )
        except Exception as err:
            msg = f"Failed to start watering: {err}"
            raise HomeAssistantError(msg) from err

    hass.services.async_register(
        DOMAIN,
        "start_watering",
        start_watering_service,
        schema=START_WATERING_SCHEMA,
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up this integration using UI."""
    session = async_get_clientsession(hass)

    hass.data[DOMAIN][entry.entry_id] = {}
    try:
        auth = MoenAuth(
            access_token=entry.data[CONF_ACCESS_TOKEN],
            refresh_token=entry.data[CONF_REFRESH_TOKEN],
            session=session,
        )
        client = MoenApiClient(auth=auth, session=session)
        hass.data[DOMAIN][entry.entry_id][CLIENT] = client
        user = await client.async_get_user()
        resp = await client.async_get_devices()
    except MoenApiAuthenticationError as err:
        raise ConfigEntryAuthFailed(err) from err
    except MoenApiError as err:
        raise ConfigEntryNotReady(err) from err
    _LOGGER.debug("INITIAL devices: %s", resp)

    devices = _build_coordinators(hass, entry, client, resp["devices"])
    if needs_info := [d for d in devices if d.needs_legacy_info]:
        await _async_add_legacy_info(client, needs_info)
    hass.data[DOMAIN][entry.entry_id]["devices"] = devices

    tasks = [device.async_config_entry_first_refresh() for device in devices]
    await asyncio.gather(*tasks)

    # One MQTT connection for the account; each device adds its own topics.
    mqtt_client = MoenMqttClient(auth=auth, legacy_id=user["legacyId"])
    for device in devices:
        device.subscribe_mqtt(mqtt_client)
    hass.data[DOMAIN][entry.entry_id][MQTT_TASK] = entry.async_create_background_task(
        hass, mqtt_client.async_run(), name=f"{DOMAIN}_mqtt"
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


def _build_coordinators(
    hass: HomeAssistant,
    entry: ConfigEntry,
    client: MoenApiClient,
    device_list: list[dict[str, Any]],
) -> list[MoenBaseCoordinator]:
    """Create a coordinator for each supported device type."""
    devices: list[MoenBaseCoordinator] = []
    for device in device_list:
        device_type = device.get("type")
        if (coordinator_cls := COORDINATOR_TYPES.get(device_type)) is None:
            _LOGGER.debug(
                "Skipping unsupported device type %s (%s)",
                device_type,
                device.get("nickname"),
            )
            continue
        devices.append(
            coordinator_cls(hass, client, device["duid"], device, config_entry=entry)
        )
    return devices


async def _async_add_legacy_info(
    client: MoenApiClient, devices: list[MoenBaseCoordinator]
) -> None:
    """Attach app-API device info (Cognito id, model details) to devices."""
    try:
        legacy_devices = await client.async_get_legacy_devices()
    except MoenApiError as err:
        _LOGGER.debug("Legacy device list unavailable: %s", err)
        return
    by_client_id = {str(d.get("clientId")): d for d in legacy_devices}
    for device in devices:
        device.set_legacy_info(by_client_id.get(device.client_id, {}))


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Allow deleting a device in the UI once the Moen account stops reporting it."""
    devices = hass.data[DOMAIN].get(entry.entry_id, {}).get("devices", [])
    current = {(DOMAIN, device.id) for device in devices}
    return not device_entry.identifiers & current


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        entry_data = hass.data[DOMAIN].pop(entry.entry_id)
        if (mqtt_task := entry_data.get(MQTT_TASK)) is not None:
            mqtt_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await mqtt_task
        for device in entry_data.get("devices", []):
            await device.async_shutdown()
    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
