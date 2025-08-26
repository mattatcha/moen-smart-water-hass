"""DataUpdateCoordinator for integration_blueprint."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from custom_components.moen_smart_water_network.types import (
    CoordinatorData,
    DeviceData,
)

from .api import (
    ApiClient,
    ApiClientAuthenticationError,
    ApiClientError,
)
from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from custom_components.moen_smart_water_network.types import (
        ZoneData,
    )

_LOGGER = logging.getLogger(__name__)


def merge(a: dict, b: dict, path: list | None = None) -> dict:
    """Merge b into a."""
    if path is None:
        path = []
    for key, value in b.items():
        if key in a:
            if isinstance(a[key], dict) and isinstance(value, dict):
                merge(a[key], value, [*path, str(key)])
            elif a[key] == value:
                pass  # same leaf value
            else:
                a[key] = value
        else:
            a[key] = value
    return a


class MoenDataUpdateCoordinator(DataUpdateCoordinator[CoordinatorData]):
    """Class to manage fetching data from the API."""

    def __init__(
        self, hass: HomeAssistant, client: ApiClient, device_id: str, data: DeviceData
    ) -> None:
        """Initialize."""
        self.hass: HomeAssistant = hass
        self.client: ApiClient = client
        self._manufacturer: str = "Moen"
        self._device_id: str = device_id
        self._device_information: DeviceData = data
        self._schedules: dict[str, Any] = {}
        self._shadow_state: dict[str, Any] = {}

        super().__init__(
            hass=hass,
            logger=LOGGER,
            name=f"{DOMAIN}-{device_id}",
            update_interval=timedelta(seconds=15),
        )

        self._task = hass.loop.create_task(
            client.async_subscribe(data["clientId"], callback=self._subscribe_update_cb)
        )

    @callback
    def _subscribe_update_cb(self, msg: Any) -> None:
        _LOGGER.debug("mqtt: received message of type %s: %s", type(msg).__name__, msg)

        if hasattr(msg, "current"):
            if hasattr(msg.current.state, "desired"):
                _LOGGER.debug(
                    "mqtt: current desired state: %s", msg.current.state.desired
                )

            if hasattr(msg.current.state, "reported"):
                reported = msg.current.state.reported
                _LOGGER.debug(
                    "mqtt: current reported state: %s", msg.current.state.reported
                )
                merge(self._shadow_state, reported)

                self.hass.add_job(self.async_update_listeners)
        if hasattr(msg, "state"):
            if hasattr(msg.state, "desired"):
                _LOGGER.debug("mqtt: state.desired state: %s", msg.state.desired)

            if hasattr(msg.state, "reported") and msg.state.reported is not None:
                reported = msg.state.reported
                _LOGGER.debug("mqtt: state.reported state: %s", msg.state.reported)

    async def _async_update_data(self) -> CoordinatorData:
        """Update data via library."""
        try:
            LOGGER.debug("Updating data for %s", self._device_id)
            self._device_information = await self.client.async_get_device(
                self._device_id
            )

            schedules = await self.client.async_get_schedules(self._device_id)
            self._schedules = {x["id"]: x for x in schedules["items"]}
        except ApiClientAuthenticationError as exception:
            raise ConfigEntryAuthFailed(exception) from exception
        except ApiClientError as exception:
            raise UpdateFailed(exception) from exception

        return {"device": self._device_information, "schedules": self._schedules}

    @property
    def id(self) -> str:
        """Return device id."""
        return self._device_id

    @property
    def device_name(self) -> str:
        """Return device name."""
        return self._device_information.get(
            "nickname", f"{self.manufacturer} {self.device_type}"
        )

    @property
    def manufacturer(self) -> str:
        """Return manufacturer for device."""
        return self._manufacturer

    @property
    def device_type(self) -> str:
        """Return type for device."""
        return self._device_information["type"]

    @property
    def rssi(self) -> float:
        """Return rssi for device."""
        return self._device_information["connectivity"]["rssi"]

    @property
    def firmware_version(self) -> str:
        """Return the firmware version for the device."""
        return self._device_information["firmware"]["version"]

    @property
    def last_connect_time(self) -> str:
        """Return lastConnect for device."""
        return self._device_information["lastConnect"]

    @property
    def available(self) -> bool:
        """Return True if device is available."""
        return self.last_update_success and self._device_information["connected"]

    @property
    def is_watering(self) -> bool:
        """Return True if device is watering."""
        return (
            self._device_information.get("irrigation", {})
            .get("wateringState", {})
            .get("running")
        )

    @property
    def master_valve_connected(self) -> bool:
        """Return True if master valve connected."""
        return self._device_information.get("irrigation", {}).get(
            "masterValveConnected"
        )

    @property
    def rain_sensor_connected(self) -> bool:
        """Return True if master valve connected."""
        return (
            self._device_information.get("irrigation", {})
            .get("rainSensor")
            .get("connected")
        )

    @property
    def flow_sensor_connected(self) -> bool:
        """Return True if master valve connected."""
        return (
            self._device_information.get("irrigation", {})
            .get("flowSensor")
            .get("connected")
        )

    @property
    def hydra_overview(self) -> dict:
        """Return True if master valve connected."""
        return self._shadow_state.get("hydraOverview", {})

    def zones(self) -> list[ZoneData]:
        """Return zones."""
        return self._device_information.get("irrigation", {}).get("zones", [])

    def zone_from_client_id(self, client_id: int | str) -> ZoneData | None:
        """Return zone from client id."""
        return next(
            (zone for zone in self.zones() if zone["clientId"] == str(client_id)), None
        )
