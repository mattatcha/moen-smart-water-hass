"""Binary sensor platform for moen_smart_water_network."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)

from .const import DOMAIN
from .coordinator import MoenDataUpdateCoordinator
from .entity import MoenEntity

_LOGGER = logging.getLogger(__name__)

ENTITY_DESCRIPTIONS = (
    BinarySensorEntityDescription(
        key="moen_smart_water_network",
        name="Integration Blueprint Binary Sensor",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
)


# async def async_setup_entry(hass, entry, async_add_devices):
#     """Set up the binary_sensor platform."""
#     coordinator = hass.data[DOMAIN][entry.entry_id]
#     async_add_devices(
#         BinarySensor(
#             coordinator=coordinator,
#             entity_description=entity_description,
#         )
#         for entity_description in ENTITY_DESCRIPTIONS
#     )


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
    # _LOGGER.debug("devices: %s", devices)
    for device in devices:
        # _LOGGER.debug("device: %s", device.data)
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
        """Return a unique id"""
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
