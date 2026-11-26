"""Update platform for moen_smart_water_network."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.update import UpdateEntity
from homeassistant.const import EntityCategory

from .coordinator import MoenBaseCoordinator
from .entity import MoenEntity, build_entities

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the update platform."""
    async_add_entities(
        build_entities(
            hass,
            config_entry,
            # Every device type reports its firmware.
            {MoenBaseCoordinator: lambda device: [FirmwareUpdate(device)]},
        )
    )


class FirmwareUpdate(MoenEntity, UpdateEntity):
    """Installed and latest firmware of a device (read-only; no install)."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "firmware"
    _device: MoenBaseCoordinator

    def __init__(self, device: MoenBaseCoordinator) -> None:
        """Initialize the update entity."""
        super().__init__(device)
        self._attr_unique_id = f"{device.id}_firmware"

    @property
    def installed_version(self) -> str | None:
        """Return the installed firmware version."""
        return (
            self._device.latest_firmware.get("current") or self._device.firmware_version
        )

    @property
    def latest_version(self) -> str | None:
        """Return the latest firmware Moen offers; None (unknown) until checked."""
        return self._device.latest_firmware.get("latest")
