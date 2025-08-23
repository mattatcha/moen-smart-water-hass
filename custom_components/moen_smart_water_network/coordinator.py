"""DataUpdateCoordinator for integration_blueprint."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import (
    ApiClient,
    ApiClientAuthenticationError,
    ApiClientError,
)
from .const import DOMAIN, LOGGER

_LOGGER = logging.getLogger(__name__)


def merge(a: dict, b: dict, path: list | None = None) -> dict:
    """Merges b into a"""
    if path is None:
        path = []
    for key in b:
        if key in a:
            if isinstance(a[key], dict) and isinstance(b[key], dict):
                merge(a[key], b[key], [*path, str(key)])
            elif a[key] == b[key]:
                pass  # same leaf value
            else:
                a[key] = b[key]
        else:
            a[key] = b[key]
    return a


class MoenDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    def __init__(
        self, hass: HomeAssistant, client: ApiClient, device_id: str, data: dict
    ) -> None:
        """Initialize."""
        self.hass: HomeAssistant = hass
        self.client: ApiClient = client
        self._manufacturer: str = "Moen"
        self._device_id: str = device_id
        self._device_information: dict[str, Any] = {}
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

    async def _async_update_data(self):
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

    def zones(self) -> list:
        """Return zones."""
        return self._device_information.get("irrigation", {}).get("zones", [])

    def zone(self, client_id: str) -> dict:
        """Return zone from client id."""
        zones = self._device_information.get("irrigation", {}).get("zones", {})
        return next((zone for zone in zones if zone["clientId"] == str(client_id)), {})

    def zone_from_client_id(self, client_id: int) -> dict:
        """Return zone from client id."""
        zones = self._device_information.get("irrigation", {}).get("zones", {})
        return next((zone for zone in zones if zone["clientId"] == str(client_id)), {})
