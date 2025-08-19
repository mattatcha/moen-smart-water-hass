"""Binary sensor platform for moen_smart_water_network."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)

from .const import DOMAIN
from .entity import MoenEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import MoenDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

ENTITY_DESCRIPTIONS = (
    BinarySensorEntityDescription(
        key="moen_smart_water_network",
        name="Integration Blueprint Binary Sensor",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Flo sensors from config entry."""
    devices: list[MoenDataUpdateCoordinator] = hass.data[DOMAIN][config_entry.entry_id][
        "devices"
    ]
    entities: list[BinarySensorEntity] = []
    for device in devices:
        entities.append(BinarySensor(device))
        entities.append(WateringBinarySensor(device))
    async_add_entities(entities)


class BinarySensor(MoenEntity, BinarySensorEntity):
    """moen_smart_water_network binary_sensor class."""

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
        return self._device.data.get("device")["connected"]


class WateringBinarySensor(MoenEntity, BinarySensorEntity):
    """moen_smart_water_network binary_sensor class."""

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
