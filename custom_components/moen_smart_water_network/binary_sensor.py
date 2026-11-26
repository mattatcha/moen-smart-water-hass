"""Binary sensor platform for moen_smart_water_network."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory

from .coordinator import (
    MoenBaseCoordinator,
    MoenIrrigationCoordinator,
    MoenSumpPumpCoordinator,
)
from .entity import MoenEntity, build_entities

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

# Alert id for "Water Detected" in the sump pump monitor's alert catalog.
SUMP_PUMP_ALERT_WATER_DETECTED = "250"

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Moen binary sensors from config entry."""
    async_add_entities(
        build_entities(
            hass,
            config_entry,
            {
                # Every device type reports whether it is connected.
                MoenBaseCoordinator: lambda device: [ConnectedBinarySensor(device)],
                MoenIrrigationCoordinator: _irrigation_entities,
                MoenSumpPumpCoordinator: lambda device: [
                    AcPowerBinarySensor(device),
                    SumpPumpWaterDetectedBinarySensor(device),
                ],
            },
        )
    )


def _irrigation_entities(
    device: MoenIrrigationCoordinator,
) -> list[BinarySensorEntity]:
    """Return the binary sensors of a sprinkler controller."""
    return [
        IrrigationWateringBinarySensor(device),
        IrrigationRainSensorBinarySensor(device),
        IrrigationMasterValveBinarySensor(device),
        IrrigationFlowSensorBinarySensor(device),
        *(
            IrrigationScheduleActiveBinarySensor(device, sid)
            for sid in device.data["schedules"]
        ),
    ]


class ConnectedBinarySensor(MoenEntity, BinarySensorEntity):
    """Connected binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def name(self) -> str:
        """Return the friendly name of the sensor."""
        return "Connected"

    @property
    def available(self) -> bool:
        """Stay available while disconnected so the state can show it."""
        return self._device.last_update_success

    @property
    def unique_id(self) -> str:
        """Return a unique id."""
        return f"{self._device.id}_connected"

    @property
    def is_on(self) -> bool:
        """Return true if the binary_sensor is on."""
        return self._device.connected


class IrrigationWateringBinarySensor(MoenEntity, BinarySensorEntity):
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


class IrrigationRainSensorBinarySensor(MoenEntity, BinarySensorEntity):
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


class IrrigationMasterValveBinarySensor(MoenEntity, BinarySensorEntity):
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


class IrrigationFlowSensorBinarySensor(MoenEntity, BinarySensorEntity):
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


class IrrigationScheduleActiveBinarySensor(MoenEntity, BinarySensorEntity):
    """Read-only binary sensor for irrigation schedule active state."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:calendar"

    def __init__(
        self, coordinator: MoenIrrigationCoordinator, schedule_id: str
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


class AcPowerBinarySensor(MoenEntity, BinarySensorEntity):
    """
    Whether the device is on mains (AC) power.

    Reads ``powerSource`` from the device shadow (``"ac"`` when on mains).
    """

    _attr_device_class = BinarySensorDeviceClass.POWER
    _attr_translation_key = "ac_power"

    def __init__(self, device: MoenBaseCoordinator) -> None:
        """Initialize the binary sensor."""
        super().__init__(device)
        self._attr_unique_id = f"{device.id}_ac_power"

    @property
    def is_on(self) -> bool | None:
        """Return true when the device reports AC power."""
        source = self._device.shadow.get("powerSource")
        if source is None:
            return None
        return source == "ac"

    @property
    def extra_state_attributes(self) -> dict:
        """Return the raw power source."""
        return {"power_source": self._device.shadow.get("powerSource")}


class SumpPumpWaterDetectedBinarySensor(MoenEntity, BinarySensorEntity):
    """
    Water detected, from an active "Water Detected" alert.

    Matches the sump pump monitor's alert id (``SUMP_PUMP_ALERT_WATER_DETECTED``);
    other device types may number their alerts differently.
    """

    _attr_device_class = BinarySensorDeviceClass.MOISTURE
    _attr_translation_key = "water_detected"

    def __init__(self, device: MoenSumpPumpCoordinator) -> None:
        """Initialize the binary sensor."""
        super().__init__(device)
        self._attr_unique_id = f"{device.id}_water_detected"

    @property
    def is_on(self) -> bool:
        """Return true while a "Water Detected" alert is active."""
        return any(
            str(alert.get("id")) == SUMP_PUMP_ALERT_WATER_DETECTED
            and str(alert.get("state", "")).startswith("active")
            for alert in self._device.alerts
        )
