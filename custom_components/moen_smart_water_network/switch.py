"""Switch platform for moen_smart_water_network."""
from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .coordinator import MoenDataUpdateCoordinator
from .entity import MoenEntity

_LOGGER = logging.getLogger(__name__)

ENTITY_DESCRIPTIONS = (
    SwitchEntityDescription(
        key="moen_smart_water_network",
        name="Integration Switch",
        icon="mdi:format-quote-close",
    ),
)


async def async_setup_entry(hass, entry, async_add_devices):
    """Set up the sensor platform."""
    devices: list[MoenDataUpdateCoordinator] = hass.data[DOMAIN][entry.entry_id][
        "devices"
    ]

    entities: list[Entity] = []
    for device in devices:
        # entities.extend([Sensor(device)])
        for zone in device.data["device"]["irrigation"]["zones"]:
            entities.extend([ZoneEnableSwitch(device, zone)])
        for schedule in device.data["schedules"]["items"]:
            entities.extend([ScheduleEnableSwitch(device, schedule)])
    async_add_devices(entities)


# EntityCategory.CONFIG
class ZoneEnableSwitch(MoenEntity, SwitchEntity):
    """moen_smart_water_network switch class."""

    def __init__(self, coordinator: MoenDataUpdateCoordinator, data: dict) -> None:
        """Initialize the switch class."""
        self._data = data
        self._zone_name = data["name"]
        self._zone_number = data["clientId"]
        self._zone_enabled = data["wired"]
        super().__init__(coordinator)

    @property
    def unique_id(self) -> str:
        """Return a unique id by combining controller id and zone number."""
        return f"{self._device.id}_zone_{self._data.get('clientId')}"

    @property
    def name(self) -> str:
        """Return the friendly name of the zone."""
        return f"{self._zone_name} Zone Enabled"

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the device."""
        return self._data

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self._data.get("enabled")

    async def async_turn_on(self, **_: any) -> None:
        """Turn on the switch."""
        await self._device.api.async_manual_run()
        await self._device.async_request_refresh()

    async def async_turn_off(self, **_: any) -> None:
        """Turn off the switch."""
        await self._device.api.async_set_title("foo")
        await self._device.async_request_refresh()


class ZoneRunSwitch(MoenEntity, SwitchEntity):
    """moen_smart_water_network switch class."""

    def __init__(self, coordinator: MoenDataUpdateCoordinator, data: dict) -> None:
        """Initialize the switch class."""
        self._data = data
        self._zone_name = data["name"]
        self._zone_number = data["clientId"]
        self._zone_enabled = data["wired"]
        super().__init__(coordinator)

    @property
    def unique_id(self) -> str:
        """Return a unique id by combining controller id and zone number."""
        return f"{self._device.id}_zone_{self._data.get('clientId')}"

    @property
    def name(self) -> str:
        """Return the friendly name of the zone."""
        return f"{self._zone_name} Zone Enabled"

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the device."""
        return self._data

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self._data.get("enabled")

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
    _attr_icon = "mdi:cog"

    def __init__(self, coordinator: MoenDataUpdateCoordinator, data: dict) -> None:
        """Initialize the switch class."""
        self._data = data
        self._schedule_name = data["name"]
        super().__init__(coordinator)

    @property
    def unique_id(self) -> str:
        """Return a unique id by combining controller id and zone number."""
        return f"{self._device.id}_schedule_{self._data.get('id')}"

    @property
    def name(self) -> str:
        """Return the friendly name of the zone."""
        return f"{self._schedule_name} Schedule Enabled"

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the device."""
        return next(
            item
            for item in self._device.data["schedules"]["items"]
            if item["id"] == self._data.get("id")
        )

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return (
            next(
                item
                for item in self._device.data["schedules"]["items"]
                if item["id"] == self._data.get("id")
            ).get("status")
            == "active"
        )

    async def async_turn_on(self, **_: any) -> None:
        """Turn on the switch."""
        await self._device.api.async_set_title("bar")
        await self._device.async_request_refresh()

    async def async_turn_off(self, **_: any) -> None:
        """Turn off the switch."""
        await self._device.api.async_set_title("foo")
        await self._device.async_request_refresh()
