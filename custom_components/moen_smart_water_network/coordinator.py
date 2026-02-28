"""DataUpdateCoordinator for Moen Smart Water Network."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN, LOGGER
from .moen_api import (
    MoenApiAuthenticationError,
    MoenApiClient,
    MoenApiError,
    MoenMqttClient,
)
from .moen_api.models import (
    CoordinatorData,
    DeviceData,
    IrrigationRunMessage,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from .moen_api.models import ZoneData

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

    def __init__(  # noqa: PLR0913
        self,
        hass: HomeAssistant,
        client: MoenApiClient,
        mqtt_client: MoenMqttClient,
        device_id: str,
        data: DeviceData,
        legacy_id: str,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        self.hass: HomeAssistant = hass
        self.client: MoenApiClient = client
        self._mqtt_client: MoenMqttClient = mqtt_client
        self._manufacturer: str = "Moen"
        self._device_id: str = device_id
        self._device_information: DeviceData = data
        self._legacy_id: str = legacy_id
        self._schedules: dict[str, Any] = {}
        self._shadow_state: dict[str, Any] = {}
        self._irrigation_run: IrrigationRunMessage | None = None

        super().__init__(
            hass=hass,
            logger=LOGGER,
            name=f"{DOMAIN}-{device_id}",
            update_interval=timedelta(seconds=30),
            config_entry=config_entry,
        )

        self._mqtt_task: asyncio.Task[None] | None = None
        self._client_id = data["clientId"]

    def _subscribe_update_cb(self, msg: Any) -> None:
        """Handle shadow MQTT messages (called from AWS CRT thread)."""
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
                self.hass.loop.call_soon_threadsafe(
                    self._apply_shadow_update, reported
                )
        if hasattr(msg, "state"):
            if hasattr(msg.state, "desired"):
                _LOGGER.debug("mqtt: state.desired state: %s", msg.state.desired)

            if hasattr(msg.state, "reported") and msg.state.reported is not None:
                reported = msg.state.reported
                _LOGGER.debug("mqtt: state.reported state: %s", msg.state.reported)
                self.hass.loop.call_soon_threadsafe(
                    self._apply_shadow_update, reported
                )

    async def async_start_mqtt(self) -> None:
        """Start MQTT subscription task."""
        self._mqtt_task = self.hass.async_create_task(
            self._mqtt_client.async_connect(
                client_id=self._client_id,
                duid=self._device_id,
                legacy_id=self._legacy_id,
                shadow_callback=self._subscribe_update_cb,
                async_callback=self._async_message_cb,
            )
        )

    async def async_shutdown(self) -> None:
        """Cancel MQTT task and disconnect."""
        if self._mqtt_task is not None:
            self._mqtt_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._mqtt_task
            self._mqtt_task = None
        await self._mqtt_client.async_disconnect()

    @callback
    def _apply_shadow_update(self, reported: dict) -> None:
        """Apply shadow state update on the event loop."""
        merge(self._shadow_state, reported)
        self.async_update_listeners()

    def _async_message_cb(self, message: dict[str, Any]) -> None:
        """Handle /async/{duid} MQTT messages (called from AWS CRT thread)."""
        _LOGGER.debug("async mqtt: received message: %s", message)

        event = message.get("event")
        if event == "irrigation_run_update":
            self.hass.loop.call_soon_threadsafe(
                self._apply_irrigation_run, message
            )
        else:
            _LOGGER.debug("async mqtt: unhandled event type: %s", event)

    @callback
    def _apply_irrigation_run(self, message: dict[str, Any]) -> None:
        """Apply irrigation run update on the event loop."""
        self._irrigation_run = message
        self.async_update_listeners()

    async def _async_update_data(self) -> CoordinatorData:
        """Update data via library."""
        try:
            LOGGER.debug("Updating data for %s", self._device_id)

            await self.client.async_user_presence()

            self._device_information = await self.client.async_get_device(
                self._device_id
            )

            schedules = await self.client.async_get_schedules(self._device_id)
            self._schedules = {x["id"]: x for x in schedules["items"]}
        except MoenApiAuthenticationError as exception:
            raise ConfigEntryAuthFailed(exception) from exception
        except MoenApiError as exception:
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
        """Return True if rain sensor connected."""
        return (
            self._device_information.get("irrigation", {})
            .get("rainSensor", {})
            .get("connected", False)
        )

    @property
    def flow_sensor_connected(self) -> bool:
        """Return True if flow sensor connected."""
        return (
            self._device_information.get("irrigation", {})
            .get("flowSensor", {})
            .get("connected", False)
        )

    @property
    def hydra_overview(self) -> dict:
        """Return shadow hydra overview state."""
        return self._shadow_state.get("hydraOverview", {})

    @property
    def irrigation_run(self) -> IrrigationRunMessage | None:
        """Return the latest irrigation run message from /async topic."""
        return self._irrigation_run

    @property
    def irrigation_run_status(self) -> str | None:
        """Return the current irrigation run status."""
        if self._irrigation_run is None:
            return None
        return (
            self._irrigation_run.get("body", {}).get("state", {}).get("status")
        )

    def zones(self) -> list[ZoneData]:
        """Return zones."""
        return self._device_information.get("irrigation", {}).get("zones", [])

    def zone_from_client_id(self, client_id: int | str) -> ZoneData | None:
        """Return zone from client id."""
        return next(
            (zone for zone in self.zones() if zone["clientId"] == str(client_id)), None
        )
