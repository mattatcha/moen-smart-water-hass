"""Base entity for Moen Smart Water Network."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import (
    CONF_IRRIGATION_ZONE_DURATIONS,
    DEFAULT_IRRIGATION_MANUAL_RUN_DURATION,
    DOMAIN,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .coordinator import MoenBaseCoordinator, MoenIrrigationCoordinator
    from .moen_api.models import IrrigationZoneData


def build_entities[E: Entity](
    hass: HomeAssistant,
    entry: ConfigEntry,
    factories: Mapping[type[MoenBaseCoordinator], Callable[[Any], Iterable[E]]],
) -> list[E]:
    """
    Create a platform's entities for every device on the config entry.

    ``factories`` maps a coordinator class to a function returning that
    device type's entities. A device gets the entities of every class it is
    an instance of, so a ``MoenBaseCoordinator`` factory applies to all types.
    """
    devices: list[MoenBaseCoordinator] = hass.data[DOMAIN][entry.entry_id]["devices"]
    return [
        entity
        for device in devices
        for device_cls, factory in factories.items()
        if isinstance(device, device_cls)
        for entity in factory(device)
    ]


class MoenEntity(Entity):
    """MoenEntity class."""

    _attr_force_update = False
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        device: MoenBaseCoordinator,
    ) -> None:
        """Init Moen entity."""
        self._device: Any = device
        self._state: Any = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.id)},
            manufacturer=self._device.manufacturer,
            name=self._device.device_name.capitalize(),
            model_id=self._device.device_type,
            sw_version=self._device.firmware_version,
        )

    @property
    def available(self) -> bool:
        """Return True if device is available."""
        return self._device.available

    async def async_update(self) -> None:
        """Update Moen entity."""
        await self._device.async_request_refresh()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        self.async_on_remove(self._device.async_add_listener(self.async_write_ha_state))


class MoenIrrigationZoneEntity(MoenEntity):
    """Base entity for zone-specific entities that need duration config."""

    def __init__(
        self,
        coordinator: MoenIrrigationCoordinator,
        data: IrrigationZoneData,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize with zone data and config entry."""
        self._zone_name = data["name"]
        self._zone_number = data["clientId"]
        self._zone_full_id = data["id"]
        self._config_entry = config_entry
        super().__init__(coordinator)

    def _get_duration(self) -> int:
        """Get run duration from config entry options or default."""
        durations = self._config_entry.options.get(CONF_IRRIGATION_ZONE_DURATIONS, {})
        return durations.get(
            str(self._zone_number), DEFAULT_IRRIGATION_MANUAL_RUN_DURATION
        )
