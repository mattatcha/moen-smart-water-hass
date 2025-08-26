"""BlueprintEntity class."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN

if TYPE_CHECKING:
    from .coordinator import MoenDataUpdateCoordinator


class MoenEntity(Entity):
    """MoenEntity class."""

    _attr_force_update = False
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        device: MoenDataUpdateCoordinator,
    ) -> None:
        """Init Moen entity."""
        self._device: MoenDataUpdateCoordinator = device
        self._state: Any = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.id)},
            manufacturer=self._device.manufacturer,
            name=self._device.device_name.capitalize(),
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
