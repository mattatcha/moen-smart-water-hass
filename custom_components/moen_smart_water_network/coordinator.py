"""DataUpdateCoordinator for Moen Smart Water Network."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, ClassVar

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util

from .const import DOMAIN, LOGGER
from .moen_api import (
    MoenApiAuthenticationError,
    MoenApiClient,
    MoenApiError,
    MoenMqttClient,
)
from .moen_api.const import (
    DEVICE_TYPE_HYD,
    DEVICE_TYPE_NAB,
    SUMP_PUMP_COMMAND_STREAM_OFF,
    SUMP_PUMP_COMMAND_STREAM_ON,
)
from .moen_api.models import (
    DeviceData,
    IrrigationCoordinatorData,
    IrrigationRunMessage,
    SumpPumpCoordinatorData,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from .moen_api.models import (
        ActiveAlert,
        IrrigationZoneData,
        SumpPumpCapacity,
        SumpPumpEnvironment,
        SumpPumpLastUsage,
        SumpPumpSession,
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


# How often to ask Moen for a device's latest firmware, and how soon to retry
# after a failed check.
FIRMWARE_CHECK_SECONDS = 6 * 60 * 60
FIRMWARE_RETRY_SECONDS = 15 * 60


class MoenBaseCoordinator[DataT](DataUpdateCoordinator[DataT]):
    """Shared device state, MQTT shadow handling and properties."""

    # True for device types whose API calls need the app API's device info
    # (such as the Cognito identity id). Setup fetches it only if one does.
    needs_legacy_info: ClassVar[bool] = False

    def __init__(  # noqa: PLR0913
        self,
        hass: HomeAssistant,
        client: MoenApiClient,
        device_id: str,
        data: DeviceData,
        *,
        config_entry: ConfigEntry,
        update_interval: timedelta,
    ) -> None:
        """Initialize."""
        self.hass: HomeAssistant = hass
        self.client: MoenApiClient = client
        self._manufacturer: str = "Moen"
        self._device_id: str = device_id
        self._device_information: DeviceData = data
        self._shadow_state: dict[str, Any] = {}
        self._cognito_id: str | None = None
        self.legacy_info: dict[str, Any] = {}
        self._latest_firmware: dict[str, Any] = {}
        self._next_firmware_check: float = 0.0

        super().__init__(
            hass=hass,
            logger=LOGGER,
            name=f"{DOMAIN}-{device_id}",
            update_interval=update_interval,
            config_entry=config_entry,
        )

        self._client_id: str = str(data["clientId"])

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
                self.hass.loop.call_soon_threadsafe(self._apply_shadow_update, reported)
        if hasattr(msg, "state"):
            if hasattr(msg.state, "desired"):
                _LOGGER.debug("mqtt: state.desired state: %s", msg.state.desired)

            if hasattr(msg.state, "reported") and msg.state.reported is not None:
                reported = msg.state.reported
                _LOGGER.debug("mqtt: state.reported state: %s", msg.state.reported)
                self.hass.loop.call_soon_threadsafe(self._apply_shadow_update, reported)

    def _async_message_cb(self, message: dict[str, Any]) -> None:
        """Handle /async/{duid} MQTT messages (called from AWS CRT thread)."""
        _LOGGER.debug("async mqtt: unhandled message: %s", message)

    def set_legacy_info(self, info: dict[str, Any]) -> None:
        """Store app-API device info (Cognito identity id, model details)."""
        self.legacy_info = info
        self._cognito_id = info.get("federatedIdentity")

    def diagnostics(self) -> dict[str, Any]:
        """Return this device's state for the diagnostics download."""
        data: dict[str, Any] = {
            "type": self.device_type,
            "available": self.available,
            "last_update_success": self.last_update_success,
            "data": self.data,
            "latest_firmware": self.latest_firmware,
        }
        if self.needs_legacy_info:
            data["legacy_info"] = self.legacy_info
        return data

    def subscribe_mqtt(self, mqtt_client: MoenMqttClient) -> None:
        """Register this device's topics on the account's MQTT connection."""
        mqtt_client.add_device(
            self._client_id,
            self._device_id,
            self._subscribe_update_cb,
            self._async_message_cb,
        )

    async def _async_update_data(self) -> DataT:
        """Refresh the token, the device's own data, then its firmware info."""
        await self._async_ensure_token()
        data = await self._async_update_device_data()
        await self._async_check_firmware()
        return data

    async def _async_update_device_data(self) -> DataT:
        """Fetch this device type's data; implemented by each coordinator."""
        raise NotImplementedError

    async def _async_check_firmware(self) -> None:
        """Ask Moen for the latest firmware; a failure keeps the old info."""
        now = time.monotonic()
        if now < self._next_firmware_check:
            return
        try:
            self._latest_firmware = await self.client.async_get_latest_firmware(
                self._client_id
            )
        except MoenApiAuthenticationError as exception:
            raise ConfigEntryAuthFailed(exception) from exception
        except MoenApiError as exception:
            LOGGER.debug("Firmware check for %s failed: %s", self._device_id, exception)
            self._next_firmware_check = now + FIRMWARE_RETRY_SECONDS
        else:
            self._next_firmware_check = now + FIRMWARE_CHECK_SECONDS

    async def _async_ensure_token(self) -> None:
        """
        Refresh tokens shortly before they expire.

        MQTT reconnects build AWS credentials from the id token, so it must
        not be left to expire between REST calls.
        """
        try:
            await self.client.auth.async_ensure_token()
        except MoenApiAuthenticationError as exception:
            raise ConfigEntryAuthFailed(exception) from exception
        except MoenApiError as exception:
            raise UpdateFailed(exception) from exception

    @callback
    def _apply_shadow_update(self, reported: dict) -> None:
        """Apply shadow state update on the event loop."""
        merge(self._shadow_state, reported)
        self.async_update_listeners()

    @property
    def shadow(self) -> dict[str, Any]:
        """Return the device shadow's merged ``state.reported``."""
        return self._shadow_state

    @property
    def latest_firmware(self) -> dict[str, Any]:
        """Return Moen's ``current``/``latest`` firmware info ({} until known)."""
        return self._latest_firmware

    @property
    def id(self) -> str:
        """Return device id."""
        return self._device_id

    @property
    def client_id(self) -> str:
        """Return the device's numeric client id (AWS IoT thing name)."""
        return self._client_id

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
        return self._device_information.get("type", "unknown")

    @property
    def rssi(self) -> float | None:
        """Return rssi for device."""
        return self._device_information.get("connectivity", {}).get("rssi")

    @property
    def firmware_version(self) -> str | None:
        """Return the firmware version for the device."""
        return self._device_information.get("firmware", {}).get("version")

    @property
    def last_connect_time(self) -> str | None:
        """Return lastConnect for device."""
        return self._device_information.get("lastConnect")

    @property
    def connected(self) -> bool:
        """Return True if the cloud reports the device as connected."""
        return bool(self._device_information.get("connected", False))

    @property
    def available(self) -> bool:
        """Return True if device is available."""
        return self.last_update_success and self.connected


class MoenIrrigationCoordinator(MoenBaseCoordinator[IrrigationCoordinatorData]):
    """Coordinator for a Smart Sprinkler Controller (type "hyd")."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: MoenApiClient,
        device_id: str,
        data: DeviceData,
        *,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            client,
            device_id,
            data,
            config_entry=config_entry,
            update_interval=timedelta(seconds=30),
        )
        self._schedules: dict[str, Any] = {}
        self._irrigation_run: IrrigationRunMessage | None = None

    def diagnostics(self) -> dict[str, Any]:
        """Return this device's state for the diagnostics download."""
        return {**super().diagnostics(), "hydra_overview": self.hydra_overview}

    def _async_message_cb(self, message: dict[str, Any]) -> None:
        """Handle /async/{duid} MQTT messages (called from AWS CRT thread)."""
        _LOGGER.debug("async mqtt: received message: %s", message)

        event = message.get("event")
        if event == "irrigation_run_update":
            self.hass.loop.call_soon_threadsafe(self._apply_irrigation_run, message)
        else:
            _LOGGER.debug("async mqtt: unhandled event type: %s", event)

    @callback
    def _apply_irrigation_run(self, message: dict[str, Any]) -> None:
        """Apply irrigation run update on the event loop."""
        self._irrigation_run = message
        self.async_update_listeners()

    async def _async_update_device_data(self) -> IrrigationCoordinatorData:
        """Fetch device info and schedules."""
        LOGGER.debug("Updating data for %s", self._device_id)

        # The presence "heartbeat" is a best-effort ping to tell Moen we are
        # online. Moen's API has been returning 400/401 for it, and because it
        # was the first call in the refresh, its failure aborted the whole
        # update and marked every entity unavailable. Treat it as non-fatal so
        # device/schedule data (and the MQTT shadow) keep flowing regardless.
        try:
            await self.client.async_user_presence()
        except MoenApiError as exception:
            LOGGER.debug("User presence update failed (ignored): %s", exception)

        try:
            self._device_information = await self.client.async_get_device(
                self._device_id
            )

            schedules = await self.client.async_get_irrigation_schedules(
                self._device_id
            )
            self._schedules = {x["id"]: x for x in schedules["items"]}
        except MoenApiAuthenticationError as exception:
            raise ConfigEntryAuthFailed(exception) from exception
        except MoenApiError as exception:
            raise UpdateFailed(exception) from exception

        return {"device": self._device_information, "schedules": self._schedules}

    @property
    def is_watering(self) -> bool:
        """Return True if device is watering."""
        return bool(
            self._device_information.get("irrigation", {})
            .get("wateringState", {})
            .get("running", False)
        )

    @property
    def master_valve_connected(self) -> bool:
        """Return True if master valve connected."""
        return self._device_information.get("irrigation", {}).get(
            "masterValveConnected", False
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
        return self._irrigation_run.get("body", {}).get("state", {}).get("status")

    def zones(self) -> list[IrrigationZoneData]:
        """Return zones."""
        return self._device_information.get("irrigation", {}).get("zones", [])

    def wired_zones(self) -> list[IrrigationZoneData]:
        """Return the zones with a valve wired to the controller."""
        return [zone for zone in self.zones() if zone.get("wired") is not False]

    def zone_from_client_id(self, client_id: int | str) -> IrrigationZoneData | None:
        """Return zone from client id."""
        return next(
            (zone for zone in self.zones() if zone["clientId"] == str(client_id)), None
        )

    @property
    def watering_mode(self) -> str | None:
        """Return the current watering mode."""
        return self._device_information.get("irrigation", {}).get("wateringMode")

    @property
    def active_zone_duration_remaining(self) -> int | None:
        """Return duration remaining (s) for the active zone."""
        if self._irrigation_run is None:
            return None
        planned = (
            self._irrigation_run.get("body", {}).get("state", {}).get("planned", [])
        )
        for entry in planned:
            if entry.get("isActive"):
                return entry.get("durationRemaining")
        return None

    @property
    def active_zone_id(self) -> str | None:
        """Return zone id of the currently active zone from irrigation run."""
        if self._irrigation_run is None:
            return None
        planned = (
            self._irrigation_run.get("body", {}).get("state", {}).get("planned", [])
        )
        for entry in planned:
            if entry.get("isActive"):
                return entry.get("zoneId")
        return None

    @staticmethod
    def matches_schedule_day(
        candidate: datetime,
        schedule: dict,
    ) -> bool:
        """Check if a candidate date matches a schedule's frequency."""
        frequency = schedule.get("frequency")
        if frequency == "daily":
            return True
        if frequency == "weekly":
            days = schedule.get("daysOfWeek") or []
            return candidate.strftime("%A").lower() in [d.lower() for d in days]
        if frequency == "even":
            return candidate.day % 2 == 0
        if frequency == "odd":
            return candidate.day % 2 == 1
        return False

    @property
    def next_schedule_run(self) -> datetime | None:
        """Compute the next scheduled run time from active schedules."""
        now = dt_util.now()
        next_run: datetime | None = None

        for schedule in self._schedules.values():
            if schedule.get("status") != "active":
                continue
            start_at = schedule.get("preferredTime", {}).get("startAt")
            if not start_at:
                continue
            try:
                time_parts = start_at.split(":")
                run_hour = int(time_parts[0])
                run_minute = int(time_parts[1]) if len(time_parts) > 1 else 0
            except (ValueError, IndexError):
                continue

            for day_offset in range(14):
                candidate = now + timedelta(days=day_offset)
                candidate = candidate.replace(
                    hour=run_hour,
                    minute=run_minute,
                    second=0,
                    microsecond=0,
                )
                if candidate <= now:
                    continue
                if not self.matches_schedule_day(candidate, schedule):
                    continue
                if next_run is None or candidate < next_run:
                    next_run = candidate
                break

        return next_run


# Slow-changing sump pump data (environment, pump cycles, capacity).
SUMP_PUMP_SLOW_REFRESH_SECONDS = 15 * 60
# Water level and pump state are only reported while the device streams. One
# "drop_on" starts streaming within ~10 s and it lasted 10+ minutes when tested;
# an "updates_off" (e.g. the Moen app closing) stops it immediately. So
# streaming is re-requested whenever the shadow shows it stopped, at most this
# often.
SUMP_PUMP_STREAM_RETRY_SECONDS = 60


class MoenSumpPumpCoordinator(MoenBaseCoordinator[SumpPumpCoordinatorData]):
    """Coordinator for a Smart Sump Pump Monitor (type "nab")."""

    needs_legacy_info = True

    def __init__(
        self,
        hass: HomeAssistant,
        client: MoenApiClient,
        device_id: str,
        data: DeviceData,
        *,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            client,
            device_id,
            data,
            config_entry=config_entry,
            update_interval=timedelta(seconds=60),
        )
        self._environment: SumpPumpEnvironment = {}
        self._last_usage: SumpPumpLastUsage = {}
        self._last_session: SumpPumpSession | None = None
        self._capacity: SumpPumpCapacity = {}
        self._alerts: list[ActiveAlert] = []
        self._slow_refreshed_at: float | None = None
        self._stream_requested_at: float | None = None

    async def _async_update_device_data(self) -> SumpPumpCoordinatorData:
        """Fetch shadow + alerts every update, slower data every 15 minutes."""
        try:
            shadow = await self.client.async_app_shadow_get(self._client_id)
            alerts = await self.client.async_get_active_alerts_v2()
        except MoenApiAuthenticationError as exception:
            raise ConfigEntryAuthFailed(exception) from exception
        except MoenApiError as exception:
            raise UpdateFailed(exception) from exception

        merge(self._shadow_state, shadow.get("state", {}).get("reported", {}))
        self._alerts = [a for a in alerts if str(a.get("duid")) == self._client_id]

        now = time.monotonic()
        if (
            self._slow_refreshed_at is None
            or now - self._slow_refreshed_at >= SUMP_PUMP_SLOW_REFRESH_SECONDS
        ):
            await self._async_refresh_slow_data()
            self._slow_refreshed_at = now

        if not self.is_streaming and (
            self._stream_requested_at is None
            or now - self._stream_requested_at >= SUMP_PUMP_STREAM_RETRY_SECONDS
        ):
            await self._async_send_command(SUMP_PUMP_COMMAND_STREAM_ON)
            self._stream_requested_at = now

        return self._snapshot()

    async def _async_refresh_slow_data(self) -> None:
        """Refresh slow-changing data; a failing endpoint keeps its old value."""
        cid, cog = self._client_id, self._cognito_id
        calls = {
            "_environment": self.client.async_get_sump_pump_environment(cid, cog),
            "_last_usage": self.client.async_get_sump_pump_last_usage(cid),
            "_sessions": self.client.async_get_sump_pump_sessions(cid, cog, limit=1),
            "_capacity": self.client.async_get_sump_pump_capacity(cid, cog),
        }
        results = await asyncio.gather(*calls.values(), return_exceptions=True)
        for attr, result in zip(calls, results, strict=True):
            if isinstance(result, MoenApiAuthenticationError):
                raise ConfigEntryAuthFailed(result) from result
            if isinstance(result, BaseException):
                LOGGER.debug("Sump pump %s refresh failed: %s", attr, result)
                continue
            if attr == "_sessions":
                self._last_session = result[0] if result else None
            elif isinstance(result, dict):
                setattr(self, attr, result)

    async def _async_send_command(self, command: str) -> None:
        """Send a streaming command; failures are logged, not fatal."""
        try:
            await self.client.async_sump_pump_command(self._client_id, command)
        except MoenApiError as exception:
            LOGGER.debug("Sump pump command %s failed: %s", command, exception)

    async def async_shutdown(self) -> None:
        """Stop device streaming, then disconnect."""
        if self._stream_requested_at is not None:
            self._stream_requested_at = None
            await self._async_send_command(SUMP_PUMP_COMMAND_STREAM_OFF)
        await super().async_shutdown()

    def _snapshot(self) -> SumpPumpCoordinatorData:
        """Return the current data as a coordinator data dict."""
        return {
            "device": self._device_information,
            "shadow": self._shadow_state,
            "environment": self._environment,
            "last_usage": self._last_usage,
            "last_session": self._last_session,
            "capacity": self._capacity,
            "alerts": self._alerts,
        }

    @property
    def droplet(self) -> dict[str, Any]:
        """Return the water level block of the shadow."""
        return self._shadow_state.get("droplet") or {}

    @property
    def is_streaming(self) -> bool:
        """Return True while the device reports water level / pump state."""
        return self.droplet.get("floodRisk") not in (None, "unknown")

    @property
    def environment(self) -> SumpPumpEnvironment:
        """Return the latest temperature/humidity data."""
        return self._environment

    @property
    def last_usage(self) -> SumpPumpLastUsage:
        """Return the last pump cycle summary."""
        return self._last_usage

    @property
    def last_session(self) -> SumpPumpSession | None:
        """Return the most recent pump cycle."""
        return self._last_session

    @property
    def capacity(self) -> SumpPumpCapacity:
        """Return the primary pump capacity assessment."""
        return self._capacity

    @property
    def alerts(self) -> list[ActiveAlert]:
        """Return this device's active alerts."""
        return self._alerts

    @property
    def rssi(self) -> float | None:
        """Return Wi-Fi signal strength."""
        return self._shadow_state.get("wifiRssi", super().rssi)

    @property
    def firmware_version(self) -> str | None:
        """Return the firmware version."""
        return self._shadow_state.get("firmwareVersion") or super().firmware_version

    @property
    def connected(self) -> bool:
        """Return True if the device is connected to the cloud."""
        if "connected" in self._shadow_state:
            return bool(self._shadow_state["connected"])
        return super().connected


# Coordinator for each supported API device ``type``. Devices of other types
# (such as "flo" shutoff valves, handled by the core "flo" integration) are
# skipped.
COORDINATOR_TYPES: dict[str, type[MoenBaseCoordinator]] = {
    DEVICE_TYPE_HYD: MoenIrrigationCoordinator,
    DEVICE_TYPE_NAB: MoenSumpPumpCoordinator,
}
