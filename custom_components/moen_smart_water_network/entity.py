"""Base entity for Moen Smart Water Network."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import CONF_ZONE_DURATIONS, DEFAULT_MANUAL_RUN_DURATION, DOMAIN

# Home Assistant replaced DeviceInfo's ``via_device`` (the hub's identifiers)
# with ``via_device_id`` (the hub's registry id); ``via_device`` stops working
# in 2027.8. Older releases reject the new key, so use whichever is supported.
VIA_DEVICE_ID_SUPPORTED = "via_device_id" in (
    DeviceInfo.__required_keys__ | DeviceInfo.__optional_keys__
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from .coordinator import MoenDataUpdateCoordinator
    from .moen_api.models import SoilSensorData, ZoneData


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


class MoenZoneEntity(MoenEntity):
    """Base entity for zone-specific entities that need duration config."""

    def __init__(
        self,
        coordinator: MoenDataUpdateCoordinator,
        data: ZoneData,
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
        durations = self._config_entry.options.get(CONF_ZONE_DURATIONS, {})
        return durations.get(str(self._zone_number), DEFAULT_MANUAL_RUN_DURATION)


class MoenSoilSensorEntity(MoenEntity):
    """
    Base entity for a wireless soil sensor paired to a controller.

    Each soil sensor is its own device, reached through the controller
    (``via_device``). It is a separate product with its own battery, radio, and
    firmware, so it is not modeled as a child device of the controller.
    """

    # Whether the entity shows a reading that goes stale when the sensor drops
    # off the network (moisture, temperature) rather than link/battery state.
    _requires_connection = False

    def __init__(
        self, coordinator: MoenDataUpdateCoordinator, data: SoilSensorData
    ) -> None:
        """Initialize with the soil sensor's initial data."""
        self._sensor_duid = data["duid"]
        self._initial_nickname = data.get("nickname") or "Soil Sensor"
        self._initial_firmware = data.get("firmwareVersion")
        super().__init__(coordinator)

    @property
    def _sensor(self) -> SoilSensorData | None:
        """Return the soil sensor's current data."""
        return self._device.soil_sensor(self._sensor_duid)

    @property
    def device_info(self) -> DeviceInfo:
        """Return the soil sensor device, connected via the controller."""
        sensor = self._sensor or {}
        firmware = sensor.get("firmwareVersion", self._initial_firmware)
        info: dict[str, Any] = {
            "identifiers": {(DOMAIN, self._sensor_duid)},
            "manufacturer": self._device.manufacturer,
            "model": "Soil Sensor",
            "model_id": sensor.get("type", "slsr"),
            "name": sensor.get("nickname", self._initial_nickname),
            # The device reports "-1" while it is offline.
            "sw_version": firmware if firmware not in (None, "-1") else None,
        }
        if VIA_DEVICE_ID_SUPPORTED and self._device.registry_device_id is not None:
            info["via_device_id"] = self._device.registry_device_id
        else:
            info["via_device"] = (DOMAIN, self._device.id)
        return DeviceInfo(**info)

    @property
    def available(self) -> bool:
        """Return True if the controller and this soil sensor are available."""
        sensor = self._sensor
        if not self._device.available or sensor is None:
            return False
        if self._requires_connection:
            return bool(sensor.get("connected"))
        return True
