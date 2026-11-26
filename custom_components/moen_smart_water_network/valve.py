"""Valve platform for moen_smart_water_network."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.valve import (
    ValveDeviceClass,
    ValveEntity,
    ValveEntityFeature,
)

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
    """Set up the valve platform."""
    async_add_entities(
        build_entities(
            hass,
            config_entry,
            {
                MoenIrrigationCoordinator: lambda device: [
                    IrrigationZoneValve(device, zone, config_entry)
                    for zone in device.wired_zones()
                ]
            },
        )
    )


class IrrigationZoneValve(MoenIrrigationZoneEntity, ValveEntity):
    """Valve entity representing an irrigation zone."""

    _attr_device_class = ValveDeviceClass.WATER
    _attr_supported_features = ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE
    _attr_reports_position = False

    @property
    def unique_id(self) -> str:
        """Return a unique id."""
        return f"{self._device.id}_zone_{self._zone_number}_valve"

    @property
    def name(self) -> str:
        """Return the friendly name of the valve."""
        return f"{self._zone_name} Zone Valve"

    @property
    def is_closed(self) -> bool:
        """Return true if the valve is closed."""
        return str(self._device.hydra_overview.get("zoneID")) != str(self._zone_number)

    async def async_open_valve(self, **kwargs: Any) -> None:  # noqa: ARG002
        """Open the valve (start watering)."""
        duration = self._get_duration()
        zones = [{"id": self._zone_full_id, "duration": duration}]
        await self._device.client.async_create_irrigation_manual_plan(
            device_id=self._device.id,
            name="Home Assistant Manual Run",
            zones=zones,
        )
        await self._device.async_request_refresh()

    async def async_close_valve(self, **kwargs: Any) -> None:  # noqa: ARG002
        """Close the valve — not yet supported by the Moen API."""
        _LOGGER.warning(
            "Stopping watering is not yet supported by the Moen API for zone %s",
            self._zone_name,
        )
