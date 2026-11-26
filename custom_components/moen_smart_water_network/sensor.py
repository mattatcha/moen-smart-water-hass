"""Sensor platform for moen_smart_water_network."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .entity import MoenEntity, MoenSoilSensorEntity, MoenZoneEntity

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback
    from homeassistant.helpers.typing import StateType

    from .coordinator import MoenDataUpdateCoordinator
    from .moen_api.models import SoilSensorData

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
                ActiveAlertsSensor(device),
                SeasonalAdjustmentSensor(device),
            ]
        )
        entities.extend(
            ZoneLastWateredSensor(device, zone, config_entry)
            for zone in device.zones()
            if zone.get("wired") is not False
        )
        entities.extend(
            SoilSensorSensor(device, soil_sensor, description)
            for soil_sensor in device.soil_sensors()
            for description in SOIL_SENSOR_DESCRIPTIONS
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


class ActiveAlertsSensor(MoenEntity, SensorEntity):
    """Number of active alerts on the controller."""

    _attr_name = "Active Alerts"
    _attr_icon = "mdi:alert-circle-outline"
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def unique_id(self) -> str:
        """Return a unique id."""
        return f"{self._device.id}_active_alerts"

    @property
    def native_value(self) -> int | None:
        """Return the number of active alerts."""
        return self._device.active_alert_count

    @property
    def extra_state_attributes(self) -> dict[str, int]:
        """Return active alert counts by severity."""
        return self._device.active_alert_counts


class SeasonalAdjustmentSensor(MoenEntity, SensorEntity):
    """Seasonal watering adjustment for the current month."""

    _attr_name = "Seasonal Adjustment"
    _attr_icon = "mdi:calendar-month"
    _attr_native_unit_of_measurement = PERCENTAGE

    @property
    def unique_id(self) -> str:
        """Return a unique id."""
        return f"{self._device.id}_seasonal_adjustment"

    @property
    def native_value(self) -> int | None:
        """Return the seasonal adjustment percentage for the current month."""
        return self._device.seasonal_adjustment


class ZoneLastWateredSensor(MoenZoneEntity, RestoreSensor):
    """
    When a zone last finished watering.

    Completed runs only arrive as real-time irrigation run messages, so the
    last value is restored across restarts.
    """

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:sprinkler-variant"

    _restored: datetime | None = None

    @property
    def unique_id(self) -> str:
        """Return a unique id."""
        return f"{self._device.id}_zone_{self._zone_number}_last_watered"

    @property
    def name(self) -> str:
        """Return the friendly name."""
        return f"{self._zone_name} Last Watered"

    async def async_added_to_hass(self) -> None:
        """Restore the last known value."""
        await super().async_added_to_hass()
        if (last := await self.async_get_last_sensor_data()) is None:
            return
        value = last.native_value
        if isinstance(value, str):
            value = dt_util.parse_datetime(value)
        if value is not None and hasattr(value, "tzinfo"):
            self._restored = value

    @property
    def native_value(self) -> datetime | None:
        """Return the most recent completed run for this zone."""
        seen = self._device.zone_last_watered(self._zone_number)
        if seen is None or (self._restored is not None and self._restored > seen):
            return self._restored
        return seen


def _soil_reading(key: str) -> Callable[[SoilSensorData], StateType]:
    """Return a value function reading one ``soilSensor`` field."""
    return lambda sensor: (sensor.get("soilSensor") or {}).get(key)


def _soil_last_report(sensor: SoilSensorData) -> datetime | None:
    """Return when the soil sensor last reported."""
    last_report = (sensor.get("soilSensor") or {}).get("lastReport")
    return dt_util.parse_datetime(last_report) if last_report else None


@dataclass(frozen=True, kw_only=True)
class SoilSensorEntityDescription(SensorEntityDescription):
    """Describes a wireless soil sensor reading."""

    value_fn: Callable[[SoilSensorData], StateType | datetime]
    # Readings go stale while the sensor is offline, so hide them then.
    requires_connection: bool = False
    # Key in the linked zone's soil sensor config holding this reading's
    # watering-skip threshold.
    threshold_key: str | None = None


SOIL_SENSOR_DESCRIPTIONS: tuple[SoilSensorEntityDescription, ...] = (
    *(
        SoilSensorEntityDescription(
            key=f"moisture_depth{depth}",
            name=f"Moisture ({depth} in)",
            device_class=SensorDeviceClass.MOISTURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=PERCENTAGE,
            suggested_display_precision=1,
            value_fn=_soil_reading(f"depth{depth}"),
            requires_connection=True,
            threshold_key=f"depth{depth}Threshold",
        )
        for depth in (1, 3, 5)
    ),
    SoilSensorEntityDescription(
        key="soil_temperature",
        name="Soil Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=_soil_reading("temp"),
        requires_connection=True,
        threshold_key="tempThreshold",
    ),
    SoilSensorEntityDescription(
        key="battery",
        name="Battery",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda sensor: (sensor.get("battery") or {}).get("percentage"),
    ),
    SoilSensorEntityDescription(
        key="signal_strength",
        name="Signal Strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda sensor: (sensor.get("connectivity") or {}).get("rssi"),
    ),
    SoilSensorEntityDescription(
        key="last_report",
        name="Last Report",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_soil_last_report,
    ),
)


class SoilSensorSensor(MoenSoilSensorEntity, SensorEntity):
    """A reading from a wireless soil sensor."""

    entity_description: SoilSensorEntityDescription

    def __init__(
        self,
        coordinator: MoenDataUpdateCoordinator,
        data: SoilSensorData,
        description: SoilSensorEntityDescription,
    ) -> None:
        """Initialize the soil sensor reading."""
        self.entity_description = description
        self._requires_connection = description.requires_connection
        super().__init__(coordinator, data)
        self._attr_unique_id = f"{self._sensor_duid}_{description.key}"

    @property
    def native_value(self) -> StateType | datetime:
        """Return the reading."""
        sensor = self._sensor
        return None if sensor is None else self.entity_description.value_fn(sensor)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the linked zone and its watering-skip threshold."""
        threshold_key = self.entity_description.threshold_key
        if threshold_key is None:
            return None
        attributes: dict[str, Any] = {}
        if (zone := self._device.soil_sensor_zone(self._sensor_duid)) is not None:
            attributes["linked_zone"] = zone.get("name")
        config = self._device.soil_sensor_zone_config(self._sensor_duid) or {}
        if (threshold := config.get(threshold_key)) is not None:
            # Thresholds are stored as reported: percent for moisture and
            # degrees Celsius for temperature.
            key = (
                "skip_threshold_celsius"
                if threshold_key == "tempThreshold"
                else "skip_threshold"
            )
            attributes[key] = threshold
        return attributes or None
