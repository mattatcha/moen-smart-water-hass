"""Sensor platform for moen_smart_water_network."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.util import dt as dt_util

from .coordinator import (
    MoenBaseCoordinator,
    MoenIrrigationCoordinator,
    MoenSumpPumpCoordinator,
)
from .entity import MoenEntity, build_entities

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    async_add_entities(
        build_entities(
            hass,
            config_entry,
            {
                # Every device type reports its WiFi signal strength.
                MoenBaseCoordinator: lambda device: [RssiSensor(device)],
                MoenIrrigationCoordinator: lambda device: [
                    IrrigationStateSensor(device),
                    IrrigationRunningZoneNameSensor(device),
                    IrrigationNextScheduleRunSensor(device),
                    IrrigationRunRemainingSensor(device),
                    IrrigationWateringModeSensor(device),
                ],
                MoenSumpPumpCoordinator: lambda device: [
                    SumpPumpSensor(device, description)
                    for description in SUMP_PUMP_SENSORS
                ],
            },
        )
    )


class IrrigationStateSensor(MoenEntity, SensorEntity):
    """Sprinkler controller state sensor."""

    _attr_name = "State"

    @property
    def unique_id(self) -> str:
        """Return the unique ID for the device sensor."""
        return f"{self._device.id}_state"

    @property
    def native_value(self) -> str:
        """Return the native value of the sensor."""
        return self._device.hydra_overview.get("status", "unknown")


class IrrigationRunningZoneNameSensor(MoenEntity, SensorEntity):
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


class IrrigationNextScheduleRunSensor(MoenEntity, SensorEntity):
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


class IrrigationRunRemainingSensor(MoenEntity, SensorEntity):
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


class IrrigationWateringModeSensor(MoenEntity, SensorEntity):
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


# --- Sump pump monitor ---

# Shadow values the cloud reports while the device is not streaming.
_NOT_STREAMING = {"unknown", None}
_TEMPERATURE_UNITS = {
    "F": UnitOfTemperature.FAHRENHEIT,
    "C": UnitOfTemperature.CELSIUS,
}


def _droplet(device: MoenSumpPumpCoordinator, key: str) -> Any:
    """Return a water level field, or None while the device isn't streaming."""
    value = device.droplet.get(key)
    return None if value in _NOT_STREAMING else value


def _water_level(device: MoenSumpPumpCoordinator) -> int | None:
    """Return the raw water level; -1 means the device isn't streaming."""
    level = device.droplet.get("level")
    if not isinstance(level, (int, float)) or level < 0:
        return None
    return level


def _parse_time(value: Any) -> datetime | None:
    """Parse an ISO 8601 timestamp, returning None for missing values."""
    if not isinstance(value, str):
        return None
    return dt_util.parse_datetime(value)


def _session(device: MoenSumpPumpCoordinator, key: str) -> Any:
    """Return a field of the most recent pump cycle."""
    return (device.last_session or {}).get(key)


def _ms_to_s(value: Any) -> float | None:
    """Convert milliseconds to seconds."""
    if not isinstance(value, (int, float)):
        return None
    return round(value / 1000, 1)


def _pump_out_rate(device: MoenSumpPumpCoordinator) -> float | None:
    """Return the last cycle's pump-out rate (the app's "Water Out" gpm)."""
    volume = _session(device, "emptyVolume")
    run_ms = _session(device, "emptyTimeMS")
    if not isinstance(volume, (int, float)) or not isinstance(run_ms, (int, float)):
        return None
    if run_ms <= 0:
        return None
    return round(volume / (run_ms / 60000), 2)


def _peak_capacity(device: MoenSumpPumpCoordinator) -> int | None:
    """Return the highest of the primary pump's highest capacity days."""
    days = device.capacity.get("TopTen") or []
    values = [d["capacity"] for d in days if isinstance(d.get("capacity"), int)]
    return max(values) if values else None


def _env(device: MoenSumpPumpCoordinator, block: str, key: str) -> Any:
    """Return a field from the environment data."""
    return device.environment.get(block, {}).get(key)


def _backup_test_attrs(device: MoenSumpPumpCoordinator) -> dict[str, Any]:
    """Return the last backup test result (omitted when it never ran)."""
    result = device.shadow.get("bckTstResults") or {}
    timestamp = result.get("timestamp")
    if isinstance(timestamp, str) and timestamp.startswith("1970-"):
        timestamp = None
    return {"last_result": result.get("status"), "last_result_time": timestamp}


def _alert_settings_attrs(device: MoenSumpPumpCoordinator) -> dict[str, Any]:
    """Return device alert settings (read-only; not editable in the app)."""
    shadow = device.shadow
    return {
        "beeper_siren_enabled": shadow.get("beeperSirenEnable"),
        "beeper_piezo_enabled": shadow.get("beeperPiezoEnable"),
        # The environment endpoint reports these in the app's unit (°F); the
        # shadow stores them in °C.
        "temperature_low_threshold": _env(device, "tempData", "tempLowThreshold"),
        "temperature_high_threshold": _env(device, "tempData", "tempHighThreshold"),
        "humidity_low_threshold": _env(device, "humidData", "humidLowThreshold"),
        "humidity_high_threshold": _env(device, "humidData", "humidHighThreshold"),
    }


def _alerts_attrs(device: MoenSumpPumpCoordinator) -> dict[str, Any]:
    """Return the device's active alerts."""
    keys = ("id", "title", "severity", "time", "state")
    return {"alerts": [{k: a.get(k) for k in keys} for a in device.alerts]}


@dataclass(frozen=True, kw_only=True)
class SumpPumpSensorEntityDescription(SensorEntityDescription):
    """Describes a sump pump monitor sensor."""

    value_fn: Callable[[MoenSumpPumpCoordinator], Any]
    attrs_fn: Callable[[MoenSumpPumpCoordinator], dict[str, Any]] | None = None


SUMP_PUMP_SENSORS: tuple[SumpPumpSensorEntityDescription, ...] = (
    SumpPumpSensorEntityDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: _env(d, "tempData", "current"),
    ),
    SumpPumpSensorEntityDescription(
        key="humidity",
        translation_key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda d: _env(d, "humidData", "current"),
    ),
    SumpPumpSensorEntityDescription(
        key="battery",
        translation_key="battery",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.shadow.get("batteryPercentage"),
    ),
    SumpPumpSensorEntityDescription(
        key="last_pump_cycle",
        translation_key="last_pump_cycle",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: _parse_time(d.last_usage.get("lastOutgoTime")),
        attrs_fn=lambda d: {"backup_used": d.last_usage.get("backupUsed")},
    ),
    SumpPumpSensorEntityDescription(
        key="estimated_next_pump_cycle",
        translation_key="estimated_next_pump_cycle",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: _parse_time(d.last_usage.get("estimatedNextRun")),
    ),
    SumpPumpSensorEntityDescription(
        key="last_cycle_volume",
        translation_key="last_cycle_volume",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        value_fn=lambda d: _session(d, "emptyVolume"),
        attrs_fn=lambda d: {
            "cycle_time": _session(d, "date"),
            "backup_ran": _session(d, "backupRan"),
        },
    ),
    SumpPumpSensorEntityDescription(
        key="last_cycle_run_time",
        translation_key="last_cycle_run_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fn=lambda d: _ms_to_s(_session(d, "emptyTimeMS")),
    ),
    SumpPumpSensorEntityDescription(
        key="last_cycle_pump_out_rate",
        translation_key="last_cycle_pump_out_rate",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.GALLONS_PER_MINUTE,
        value_fn=_pump_out_rate,
    ),
    SumpPumpSensorEntityDescription(
        key="last_cycle_inflow_rate",
        translation_key="last_cycle_inflow_rate",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.GALLONS_PER_MINUTE,
        value_fn=lambda d: _session(d, "fillVolume"),
    ),
    SumpPumpSensorEntityDescription(
        key="last_cycle_fill_time",
        translation_key="last_cycle_fill_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        value_fn=lambda d: _ms_to_s(_session(d, "fillTimeMS")),
    ),
    SumpPumpSensorEntityDescription(
        key="flood_risk",
        translation_key="flood_risk",
        value_fn=lambda d: _droplet(d, "floodRisk"),
    ),
    SumpPumpSensorEntityDescription(
        key="water_level_trend",
        translation_key="water_level_trend",
        value_fn=lambda d: _droplet(d, "trend"),
    ),
    SumpPumpSensorEntityDescription(
        key="primary_pump_state",
        translation_key="primary_pump_state",
        value_fn=lambda d: _droplet(d, "primaryState"),
    ),
    SumpPumpSensorEntityDescription(
        key="backup_pump_state",
        translation_key="backup_pump_state",
        value_fn=lambda d: _droplet(d, "backupState"),
    ),
    SumpPumpSensorEntityDescription(
        key="water_level",
        translation_key="water_level",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=_water_level,
    ),
    SumpPumpSensorEntityDescription(
        key="primary_pump_capacity",
        translation_key="primary_pump_capacity",
        value_fn=lambda d: d.capacity.get("pumpIndicator"),
        attrs_fn=lambda d: {
            "pump_capacity_sufficient": d.capacity.get("pumpCapacitySufficient"),
            "highest_capacity_days": [
                {"day": day.get("day"), "capacity": day.get("capacity")}
                for day in d.capacity.get("TopTen") or []
            ],
        },
    ),
    SumpPumpSensorEntityDescription(
        key="primary_pump_peak_capacity",
        translation_key="primary_pump_peak_capacity",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=_peak_capacity,
    ),
    SumpPumpSensorEntityDescription(
        key="backup_pump_test",
        translation_key="backup_pump_test",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.shadow.get("crockBckTst"),
        attrs_fn=_backup_test_attrs,
    ),
    SumpPumpSensorEntityDescription(
        key="alert_settings",
        translation_key="alert_settings",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.shadow.get("systemState"),
        attrs_fn=_alert_settings_attrs,
    ),
    SumpPumpSensorEntityDescription(
        key="active_alerts",
        translation_key="active_alerts",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: len(d.alerts),
        attrs_fn=_alerts_attrs,
    ),
)


class SumpPumpSensor(MoenEntity, SensorEntity):
    """Sensor for a sump pump monitor value."""

    entity_description: SumpPumpSensorEntityDescription
    _device: MoenSumpPumpCoordinator

    def __init__(
        self,
        device: MoenSumpPumpCoordinator,
        description: SumpPumpSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(device)
        self.entity_description = description
        self._attr_unique_id = f"{device.id}_{description.key}"

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        return self.entity_description.value_fn(self._device)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit, taking temperature units from the API."""
        if self.entity_description.key == "temperature":
            unit = _env(self._device, "tempData", "unitOfMeasure")
            return _TEMPERATURE_UNITS.get(unit, UnitOfTemperature.FAHRENHEIT)
        return super().native_unit_of_measurement

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self._device)
