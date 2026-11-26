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
from .entity import MoenEntity, MoenSoilSensorEntity, MoenZoneEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import MoenDataUpdateCoordinator
    from .moen_api.models import SoilSensorData

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
        entities.append(RainSensorConnectedBinarySensor(device))
        entities.append(MasterValveBinarySensor(device))
        entities.append(FlowSensorBinarySensor(device))
        entities.append(WateringRestrictedBinarySensor(device))
        entities.extend(
            ScheduleActiveBinarySensor(device, sid) for sid in device.data["schedules"]
        )
        entities.extend(
            ZoneFaultBinarySensor(device, zone, config_entry)
            for zone in device.zones()
            if zone.get("wired") is not False
        )
        entities.extend(
            SoilSensorConnectedBinarySensor(device, soil_sensor)
            for soil_sensor in device.soil_sensors()
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
    """Rain detected by the controller's rain sensor."""

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
    def available(self) -> bool:
        """Return True if the controller and its rain sensor are connected."""
        return super().available and self._device.rain_sensor_connected

    @property
    def is_on(self) -> bool | None:
        """Return true if the rain sensor reports rain."""
        return self._device.rain_detected

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        """Return the raw rain state reported by the controller."""
        return {"rain_state": self._device.hydra_overview.get("rain")}


class RainSensorConnectedBinarySensor(MoenEntity, BinarySensorEntity):
    """Rain sensor connected binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        """Return a unique id."""
        return f"{self._device.id}_rain_sensor_connected"

    @property
    def name(self) -> str:
        """Return the friendly name."""
        return "Rain Sensor Connected"

    @property
    def is_on(self) -> bool:
        """Return true if rain sensor is connected."""
        return self._device.rain_sensor_connected


class MasterValveBinarySensor(MoenEntity, BinarySensorEntity):
    """Master valve connected binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

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

    _attr_entity_category = EntityCategory.DIAGNOSTIC
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


class WateringRestrictedBinarySensor(MoenEntity, BinarySensorEntity):
    """Watering restricted on the controller."""

    _attr_icon = "mdi:water-off-outline"

    @property
    def unique_id(self) -> str:
        """Return a unique id."""
        return f"{self._device.id}_watering_restricted"

    @property
    def name(self) -> str:
        """Return the friendly name."""
        return "Watering Restricted"

    @property
    def is_on(self) -> bool | None:
        """Return true if watering is restricted."""
        return self._device.watering_restricted


class ZoneFaultBinarySensor(MoenZoneEntity, BinarySensorEntity):
    """Wiring/valve fault detected for a zone."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        """Return a unique id."""
        return f"{self._device.id}_zone_{self._zone_number}_fault"

    @property
    def name(self) -> str:
        """Return the friendly name."""
        return f"{self._zone_name} Zone Fault"

    @property
    def is_on(self) -> bool | None:
        """Return true if the zone reports a fault."""
        zone = self._device.zone_from_client_id(self._zone_number)
        if zone is None:
            return None
        return zone.get("auditStatus") == "fault" or bool(zone.get("fault"))

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        """Return the zone's audit status and fault code."""
        zone = self._device.zone_from_client_id(self._zone_number) or {}
        return {"audit_status": zone.get("auditStatus"), "fault": zone.get("fault")}


class SoilSensorConnectedBinarySensor(MoenSoilSensorEntity, BinarySensorEntity):
    """Wireless soil sensor connected to the controller."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_name = "Connected"

    def __init__(
        self, coordinator: MoenDataUpdateCoordinator, data: SoilSensorData
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, data)
        self._attr_unique_id = f"{self._sensor_duid}_connected"

    @property
    def is_on(self) -> bool | None:
        """Return true if the soil sensor is connected."""
        sensor = self._sensor
        return None if sensor is None else bool(sensor.get("connected"))
