"""Switch platform for moen_smart_water_network."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory

from .const import DOMAIN
from .entity import MoenEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity import Entity
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import MoenDataUpdateCoordinator
    from .moen_api.models import ZoneData


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_devices: AddEntitiesCallback
) -> None:
    """Set up the sensor platform."""
    devices: list[MoenDataUpdateCoordinator] = hass.data[DOMAIN][entry.entry_id][
        "devices"
    ]

    entities: list[Entity] = []
    for device in devices:
        for zone in device.data["device"]["irrigation"]["zones"]:
            if zone.get("wired") is False:
                continue
            entities.append(ZoneEnableSwitch(device, zone))
    async_add_devices(entities)


class ZoneEnableSwitch(MoenEntity, SwitchEntity):
    """Switch to enable or disable an irrigation zone."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: MoenDataUpdateCoordinator, data: ZoneData) -> None:
        """Initialize the switch class."""
        self._zone_name = data["name"]
        self._zone_id = data["clientId"]
        super().__init__(coordinator)

    def __str__(self) -> str:
        """Display the zone as a string."""
        return f'Moen Zone "{self._zone_name}" on {self._device.name}'

    @property
    def unique_id(self) -> str:
        """Return a unique id by combining controller id and zone number."""
        return f"{self._device.id}_zone_{self._zone_id}_enabled"

    @property
    def name(self) -> str:
        """Return the friendly name of the zone."""
        return f"{self._zone_name} Zone Enabled"

    @property
    def extra_state_attributes(self) -> ZoneData | None:
        """Return the state attributes of the device."""
        return self._device.zone_from_client_id(self._zone_id)

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        zone = self._device.zone_from_client_id(self._zone_id)
        if zone is not None:
            return zone.get("enabled")
        return False

    async def async_turn_on(self, **_: Any) -> None:
        """Turn on the switch."""
        await self._device.client.async_enable_zone(self._device.id, self._zone_id)
        await self._device.async_request_refresh()

    async def async_turn_off(self, **_: Any) -> None:
        """Turn off the switch."""
        await self._device.client.async_disable_zone(self._device.id, self._zone_id)
        await self._device.async_request_refresh()
