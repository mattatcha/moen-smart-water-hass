"""Binary sensor platform for moen_smart_water_network."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory

from .const import DOMAIN
from .entity import MoenEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import MoenDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Moen binary sensors from config entry."""
    devices: list[MoenDataUpdateCoordinator] = hass.data[DOMAIN][config_entry.entry_id][
        "devices"
    ]
    entities: list[BinarySensorEntity] = []
    for device in devices:
        entities.append(BinarySensor(device))
        entities.append(WateringBinarySensor(device))
        entities.append(RainSensorBinarySensor(device))
        entities.append(MasterValveBinarySensor(device))
        entities.append(FlowSensorBinarySensor(device))
        entities.extend(
            ScheduleActiveBinarySensor(device, sid) for sid in device.data["schedules"]
        )
    async_add_entities(entities)


class BinarySensor(MoenEntity, BinarySensorEntity):
    """Connected binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    @property
    def name(self) -> str:
        """Return the friendly name of the sensor."""
        return "Connected"

    @property
    def unique_id(self) -> str:
        """Return a unique id."""
        return f"{self._device.id}_connected"

    @property
    def is_on(self) -> bool:
        """Return true if the binary_sensor is on."""
        return self._device.data.get("device", {}).get("connected", False)


class WateringBinarySensor(MoenEntity, BinarySensorEntity):
    """Watering binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING

    @property
    def unique_id(self) -> str:
        """Return a unique id by combining controller id and name."""
        return f"{self._device.id}_watering"

    @property
    def name(self) -> str:
        """Return the friendly name of the sensor."""
        return "Watering"

    @property
    def is_on(self) -> bool:
        """Return true if the binary_sensor is on."""
        return self._device.is_watering


class RainSensorBinarySensor(MoenEntity, BinarySensorEntity):
    """Rain sensor connected binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.MOISTURE

    @property
    def unique_id(self) -> str:
        """Return a unique id."""
        return f"{self._device.id}_rain_sensor"

    @property
    def name(self) -> str:
        """Return the friendly name."""
        return "Rain Sensor"

    @property
    def is_on(self) -> bool:
        """Return true if rain sensor is connected."""
        return self._device.rain_sensor_connected


class MasterValveBinarySensor(MoenEntity, BinarySensorEntity):
    """Master valve connected binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    @property
    def unique_id(self) -> str:
        """Return a unique id."""
        return f"{self._device.id}_master_valve"

    @property
    def name(self) -> str:
        """Return the friendly name."""
        return "Master Valve"

    @property
    def is_on(self) -> bool:
        """Return true if master valve is connected."""
        return self._device.master_valve_connected


class FlowSensorBinarySensor(MoenEntity, BinarySensorEntity):
    """Flow sensor connected binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        """Return a unique id."""
        return f"{self._device.id}_flow_sensor"

    @property
    def name(self) -> str:
        """Return the friendly name."""
        return "Flow Sensor"

    @property
    def is_on(self) -> bool:
        """Return true if flow sensor is connected."""
        return self._device.flow_sensor_connected


class ScheduleActiveBinarySensor(MoenEntity, BinarySensorEntity):
    """Read-only binary sensor for irrigation schedule active state."""

    _attr_icon = "mdi:calendar"

    def __init__(
        self, coordinator: MoenDataUpdateCoordinator, schedule_id: str
    ) -> None:
        """Initialize the binary sensor."""
        self._id = schedule_id
        super().__init__(coordinator)

    @property
    def unique_id(self) -> str:
        """Return a unique id by combining controller id and schedule id."""
        return f"{self._device.id}_schedule_{self._id}"

    @property
    def _schedule_name(self) -> str:
        """Return the schedule name from current data."""
        return (
            self._device.data.get("schedules", {})
            .get(self._id, {})
            .get("name", "Unknown")
        )

    @property
    def name(self) -> str:
        """Return the friendly name."""
        return f"{self._schedule_name} Schedule Active"

    @property
    def extra_state_attributes(self) -> dict | None:
        """Return the state attributes of the device."""
        return self._device.data.get("schedules", {}).get(self._id)

    @property
    def is_on(self) -> bool:
        """Return true if the schedule is active."""
        return (
            self._device.data.get("schedules", {}).get(self._id, {}).get("status")
            == "active"
        )
