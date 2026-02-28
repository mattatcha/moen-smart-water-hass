"""Sensor platform for moen_smart_water_network."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.const import EntityCategory, UnitOfTime

from .const import DOMAIN
from .entity import MoenEntity

if TYPE_CHECKING:
    from datetime import datetime

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
    """Set up the sensor platform."""
    devices: list[MoenDataUpdateCoordinator] = hass.data[DOMAIN][config_entry.entry_id][
        "devices"
    ]
    entities: list[SensorEntity] = []
    for device in devices:
        entities.extend(
            [
                DeviceSensor(device),
                RunningZoneNameSensor(device),
                RssiSensor(device),
                NextScheduleRunSensor(device),
                RunRemainingSensor(device),
                WateringModeSensor(device),
            ]
        )

    async_add_entities(entities)


class DeviceSensor(MoenEntity, SensorEntity):
    """Device state sensor."""

    _attr_name = "State"

    @property
    def unique_id(self) -> str:
        """Return the unique ID for the device sensor."""
        return f"{self._device.id}_state"

    @property
    def native_value(self) -> str:
        """Return the native value of the sensor."""
        return self._device.hydra_overview.get("status", "unknown")


class RunningZoneNameSensor(MoenEntity, SensorEntity):
    """Running zone name sensor."""

    _attr_name = "Running Zone"

    @property
    def unique_id(self) -> str:
        """Return the unique ID for the running zone sensor."""
        return f"{self._device.id}_running_zone"

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra state attributes for the running zone sensor."""
        zone_id = self._device.hydra_overview.get("zoneID", -1)
        return {"client_id": zone_id}

    @property
    def native_value(self) -> str:
        """Return the native value of the sensor."""
        hydra = self._device.hydra_overview
        zone_id = hydra.get("zoneID")
        if zone_id is None:
            return "None"

        zone = self._device.zone_from_client_id(zone_id)
        if zone is None:
            return "None"

        return zone.get("name", "None")


class RssiSensor(MoenEntity, SensorEntity):
    """WiFi signal strength sensor."""

    _attr_name = "RSSI"
    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_native_unit_of_measurement = "dBm"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        """Return a unique id."""
        return f"{self._device.id}_rssi"

    @property
    def native_value(self) -> float | None:
        """Return the RSSI value."""
        return self._device.rssi


class NextScheduleRunSensor(MoenEntity, SensorEntity):
    """Next scheduled irrigation run sensor."""

    _attr_name = "Next Schedule Run"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def unique_id(self) -> str:
        """Return a unique id."""
        return f"{self._device.id}_next_schedule_run"

    @property
    def native_value(self) -> datetime | None:
        """Return the next scheduled run time."""
        return self._device.next_schedule_run


class RunRemainingSensor(MoenEntity, SensorEntity):
    """Remaining duration for the active irrigation zone."""

    _attr_name = "Run Remaining"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS

    @property
    def unique_id(self) -> str:
        """Return a unique id."""
        return f"{self._device.id}_run_remaining"

    @property
    def native_value(self) -> int | None:
        """Return the remaining duration in seconds."""
        return self._device.active_zone_duration_remaining


class WateringModeSensor(MoenEntity, SensorEntity):
    """Current watering mode sensor."""

    _attr_name = "Watering Mode"
    _attr_icon = "mdi:water-outline"

    @property
    def unique_id(self) -> str:
        """Return a unique id."""
        return f"{self._device.id}_watering_mode"

    @property
    def native_value(self) -> str | None:
        """Return the current watering mode."""
        return self._device.watering_mode
