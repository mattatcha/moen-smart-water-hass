r"""Sensor platform for moen_smart_water_network."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription

from .const import DOMAIN
from .entity import MoenEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import MoenDataUpdateCoordinator

ENTITY_DESCRIPTIONS = (
    SensorEntityDescription(
        key="moen_smart_water_network",
        name="Integration Sensor",
        icon="mdi:format-quote-close",
    ),
)
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
    entities = []
    for device in devices:
        entities.extend([DeviceSensor(device), RunningZoneNameSensor(device)])

    async_add_entities(entities)


class DeviceSensor(MoenEntity, SensorEntity):
    """moen_smart_water_network Sensor class."""

    _attr_name = "state"

    @property
    def unique_id(self) -> str:
        return f"{self._device.id}_state"

    @property
    def native_value(self) -> str:
        """Return the native value of the sensor."""
        hydra = self._device.hydra_overview

        return hydra.get("status")


class RunningZoneNameSensor(MoenEntity, SensorEntity):
    """moen_smart_water_network Sensor class."""

    _attr_name = "running zone"

    @property
    def unique_id(self) -> str:
        return f"{self._device.id}_running_zone"

    @property
    def extra_state_attributes(self):
        hydra = self._device.hydra_overview

        zone_id = hydra.get("zoneID", -1)

        return {"client_id": zone_id}

    @property
    def native_value(self) -> str:
        """Return the native value of the sensor."""
        hydra = self._device.hydra_overview

        zone_id = hydra.get("zoneID", -1)
        zone = self._device.zone_from_client_id(zone_id)

        _LOGGER.debug("zone id %s: %s", zone_id, zone)
        return zone.get("name", "None")
