"""Switch platform for moen_smart_water_network."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription

from .const import DOMAIN
from .entity import MoenEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity import Entity
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import MoenDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

ENTITY_DESCRIPTIONS = (
    SwitchEntityDescription(
        key="moen_smart_water_network",
        name="Integration Switch",
        icon="mdi:format-quote-close",
    ),
)


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
                # Exlude any zones which are not connected
                continue
            entities.extend([ZoneEnableSwitch(device, zone)])
            entities.extend([ZoneRunSwitch(device, zone)])
        for schedule_id in device.data["schedules"]:
            entities.extend([ScheduleEnableSwitch(device, schedule_id)])
    async_add_devices(entities)


# EntityCategory.CONFIG
class ZoneEnableSwitch(MoenEntity, SwitchEntity):
    """moen_smart_water_network switch class."""

    def __init__(self, coordinator: MoenDataUpdateCoordinator, data: dict) -> None:
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
    def extra_state_attributes(self):
        """Return the state attributes of the device."""
        return self._device.zone_from_client_id(self._zone_id)

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self._device.zone_from_client_id(self._zone_id).get("enabled")

    async def async_turn_on(self, **_: any) -> None:
        """Turn on the switch."""
        await self._device.client.async_zone_enable(
            self._device.id, self._zone_id, True
        )
        await self._device.async_request_refresh()

    async def async_turn_off(self, **_: any) -> None:
        """Turn off the switch."""
        await self._device.client.async_zone_enable(
            self._device.id, self._zone_id, False
        )
        await self._device.async_request_refresh()


class ZoneRunSwitch(MoenEntity, SwitchEntity):
    """moen_smart_water_network switch class."""

    _attr_icon = "mdi:valve"

    def __init__(self, coordinator: MoenDataUpdateCoordinator, data: dict) -> None:
        """Initialize the switch class."""
        self._zone_name = data["name"]
        self._zone_number = data["clientId"]
        super().__init__(coordinator)

    @property
    def unique_id(self) -> str:
        """Return a unique id by combining controller id and zone number."""
        return f"{self._device.id}_zone_{self._zone_number}"

    @property
    def name(self) -> str:
        """Return the friendly name of the zone."""
        return f"{self._zone_name} Zone Run"

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the device."""
        return self._device.zone_from_client_id(self._zone_number)

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self._device.hydra_overview.get("zoneID") == str(self._zone_number)

    async def async_turn_on(self, **_: any) -> None:
        """Turn on the switch."""
        await self._device.api.async_manual_run()
        await self._device.async_request_refresh()

    async def async_turn_off(self, **_: any) -> None:
        """Turn off the switch."""
        await self._device.api.async_set_title("foo")
        await self._device.async_request_refresh()


# EntityCategory.CONFIG
class ScheduleEnableSwitch(MoenEntity, SwitchEntity):
    """moen_smart_water_network switch class."""

    # _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:calendar"

    def __init__(
        self, coordinator: MoenDataUpdateCoordinator, schedule_id: str
    ) -> None:
        """Initialize the switch class."""
        self._id = schedule_id
        self._schedule_name = (
            coordinator.data.get("schedules").get(schedule_id).get("name")
        )
        super().__init__(coordinator)

    @property
    def unique_id(self) -> str:
        """Return a unique id by combining controller id and schedule id."""
        return f"{self._device.id}_schedule_{self._id}"

    @property
    def name(self) -> str:
        """Return the friendly name of the zone."""
        return f"{self._schedule_name} Schedule Enabled"

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the device."""
        return self._device.data.get("schedules").get(self._id)

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return (
            self._device.data.get("schedules").get(self._id).get("status") == "active"
        )

    async def async_turn_on(self, **_: any) -> None:
        """Turn on the switch."""
        await self._device.api.async_set_title("bar")
        await self._device.async_request_refresh()

    async def async_turn_off(self, **_: any) -> None:
        """Turn off the switch."""
        await self._device.api.async_set_title("foo")
        await self._device.async_request_refresh()
