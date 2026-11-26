"""Number platform for moen_smart_water_network."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import EntityCategory, UnitOfTime

from .const import CONF_IRRIGATION_ZONE_DURATIONS
from .coordinator import MoenIrrigationCoordinator
from .entity import MoenIrrigationZoneEntity, build_entities

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the number platform."""
    async_add_entities(
        build_entities(
            hass,
            config_entry,
            {
                MoenIrrigationCoordinator: lambda device: [
                    IrrigationZoneRunDurationNumber(device, zone, config_entry)
                    for zone in device.wired_zones()
                ]
            },
        )
    )


class IrrigationZoneRunDurationNumber(MoenIrrigationZoneEntity, NumberEntity):
    """Number entity for configuring zone manual run duration."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 1
    _attr_native_max_value = 60
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_icon = "mdi:timer-outline"

    @property
    def unique_id(self) -> str:
        """Return a unique id."""
        return f"{self._device.id}_zone_{self._zone_number}_duration"

    @property
    def name(self) -> str:
        """Return the friendly name."""
        return f"{self._zone_name} Run Duration"

    @property
    def native_value(self) -> float:
        """Return the current duration value."""
        return self._get_duration()

    async def async_set_native_value(self, value: float) -> None:
        """Set the run duration for this zone."""
        durations = dict(
            self._config_entry.options.get(CONF_IRRIGATION_ZONE_DURATIONS, {})
        )
        durations[str(self._zone_number)] = int(value)
        new_options = dict(self._config_entry.options)
        new_options[CONF_IRRIGATION_ZONE_DURATIONS] = durations
        self.hass.config_entries.async_update_entry(
            self._config_entry, options=new_options
        )
        self.async_write_ha_state()
