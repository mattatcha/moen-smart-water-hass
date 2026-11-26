"""MQTT connection manager for Moen Smart Water Network."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from awscrt import io, mqtt
from awsiot import iotshadow, mqtt_connection_builder

from .const import ASYNC_TOPIC, MQTT_ENDPOINT, MQTT_REGION

if TYPE_CHECKING:
    from collections.abc import Callable
    from concurrent.futures import Future

    from awscrt.auth import AwsCredentialsProvider

    from .auth import MoenAuth

_LOGGER = logging.getLogger(__name__)

io.init_logging(io.LogLevel.Warn, "stderr")

# Retry delay after a failed connection attempt; doubles up to the maximum.
# Once connected, awscrt reconnects on its own.
RETRY_MIN_SECONDS = 30
RETRY_MAX_SECONDS = 600
# Upper bound for connecting and subscribing every device.
CONNECT_TIMEOUT_SECONDS = 60


@dataclass(frozen=True, slots=True)
class _Device:
    """MQTT topics and callbacks for one device."""

    thing_name: str
    duid: str
    shadow_callback: Callable[[Any], None]
    async_callback: Callable[[dict[str, Any]], None] | None


class MoenMqttClient:
    """
    One AWS IoT MQTT connection shared by every device on an account.

    Register devices with ``add_device``, then run ``async_run`` as a
    background task. Cancelling the task disconnects.
    """

    def __init__(self, auth: MoenAuth, legacy_id: str) -> None:
        """Initialize with the auth manager and the account's legacy id."""
        self._auth = auth
        self._legacy_id = legacy_id
        self._devices: list[_Device] = []
        self._connection: mqtt.Connection | None = None
        self._shadow_client: iotshadow.IotShadowClient | None = None

    def add_device(
        self,
        thing_name: str,
        duid: str,
        shadow_callback: Callable[[Any], None],
        async_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        """Register a device's shadow and ``/async/{duid}`` topics."""
        self._devices.append(_Device(thing_name, duid, shadow_callback, async_callback))

    async def async_run(self) -> None:
        """Connect and subscribe, retrying until it works; stay connected."""
        delay = RETRY_MIN_SECONDS
        failed = False
        try:
            while True:
                try:
                    async with asyncio.timeout(CONNECT_TIMEOUT_SECONDS):
                        await self._async_connect_and_subscribe()
                    break
                # Any failure (token refresh, credentials, network, subscribe
                # timeout) is retried; the REST polling keeps entities updating.
                except Exception as err:  # noqa: BLE001
                    self._disconnect()
                    log = _LOGGER.debug if failed else _LOGGER.warning
                    log("MQTT connection failed, retrying in %ss: %s", delay, err)
                    failed = True
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, RETRY_MAX_SECONDS)
            if failed:
                _LOGGER.info("MQTT connected")
            await asyncio.Event().wait()
        finally:
            self._disconnect()

    async def _async_connect_and_subscribe(self) -> None:
        """Open the connection, subscribe every device, request each shadow."""
        # Cognito credentials need the id token, which only a refresh sets.
        await self._auth.async_ensure_token()
        credentials_provider = self._auth.create_cognito_credentials_provider(
            self._legacy_id
        )
        loop = asyncio.get_running_loop()
        # Building the connection loads TLS certificates from disk.
        self._connection = await loop.run_in_executor(
            None, partial(self._build_connection, credentials_provider)
        )
        await asyncio.wrap_future(self._connection.connect())
        _LOGGER.debug("Connected to MQTT")

        self._shadow_client = iotshadow.IotShadowClient(self._connection)
        for device in self._devices:
            await self._async_subscribe(device)
        self._request_shadows()

    def _build_connection(
        self, credentials_provider: AwsCredentialsProvider
    ) -> mqtt.Connection:
        """Build the websocket connection (blocking)."""
        # A clean session leaves nothing behind on AWS between connections;
        # _on_connection_resumed restores subscriptions after a reconnect.
        return mqtt_connection_builder.websockets_with_default_aws_signing(
            region=MQTT_REGION,
            endpoint=MQTT_ENDPOINT,
            credentials_provider=credentials_provider,
            client_id=str(uuid4()),
            clean_session=True,
            keep_alive_secs=30,
            on_connection_interrupted=lambda connection, error, **kwargs: _LOGGER.debug(
                "MQTT connection interrupted: %s", error
            ),
            on_connection_resumed=self._on_connection_resumed,
            on_connection_closed=lambda connection, callback_data, **kwargs: (
                _LOGGER.debug("MQTT connection closed: %s", callback_data)
            ),
        )

    def _on_connection_resumed(
        self,
        connection: mqtt.Connection,
        return_code: mqtt.ConnectReturnCode,
        session_present: bool,  # noqa: FBT001
        **_: Any,
    ) -> None:
        """Restore subscriptions and refresh state after awscrt reconnects."""
        _LOGGER.debug(
            "MQTT connection resumed: %s, session present: %s",
            return_code,
            session_present,
        )
        if return_code != mqtt.ConnectReturnCode.ACCEPTED:
            return
        if not session_present:
            future, _ = connection.resubscribe_existing_topics()
            future.add_done_callback(_log_failure("resubscribe"))
        # Shadow updates sent while disconnected were missed.
        self._request_shadows()

    async def _async_subscribe(self, device: _Device) -> None:
        """Subscribe to a device's shadow topics and its async topic."""
        shadow = self._shadow_client
        connection = self._connection
        if shadow is None or connection is None:
            msg = "MQTT connection not established"
            raise RuntimeError(msg)

        thing = device.thing_name
        callback = device.shadow_callback
        qos = mqtt.QoS.AT_LEAST_ONCE
        futures: list[Future] = [
            shadow.subscribe_to_update_shadow_accepted(
                iotshadow.UpdateShadowSubscriptionRequest(thing_name=thing),
                qos,
                callback,
            )[0],
            shadow.subscribe_to_get_shadow_accepted(
                iotshadow.GetShadowSubscriptionRequest(thing_name=thing),
                qos,
                callback,
            )[0],
            shadow.subscribe_to_shadow_updated_events(
                iotshadow.ShadowUpdatedSubscriptionRequest(thing_name=thing),
                qos,
                callback,
            )[0],
        ]
        if device.async_callback is not None:
            topic = ASYNC_TOPIC.format(duid=device.duid)
            futures.append(
                connection.subscribe(
                    topic, qos, partial(_on_async_message, device.async_callback)
                )[0]
            )
        await asyncio.gather(*(asyncio.wrap_future(f) for f in futures))
        _LOGGER.debug("Subscribed to MQTT topics for %s", thing)

    def _request_shadows(self) -> None:
        """Ask for every device's current shadow (delivered to its callback)."""
        if self._shadow_client is None:
            return
        for device in self._devices:
            future = self._shadow_client.publish_get_shadow(
                iotshadow.GetShadowRequest(thing_name=device.thing_name),
                mqtt.QoS.AT_LEAST_ONCE,
            )
            future.add_done_callback(_log_failure("get shadow"))

    def _disconnect(self) -> None:
        """Disconnect once; a second disconnect makes awscrt log an error."""
        if self._connection is not None:
            self._connection.disconnect()
            self._connection = None
            self._shadow_client = None


def _on_async_message(
    callback: Callable[[dict[str, Any]], None],
    topic: str,
    payload: bytes,
    **_: Any,
) -> None:
    """Decode an ``/async/{duid}`` message and pass it on (awscrt thread)."""
    try:
        message = json.loads(payload)
    except ValueError:
        _LOGGER.warning("Invalid JSON on MQTT topic %s", topic)
        return
    callback(message)


def _log_failure(action: str) -> Callable[[Future], None]:
    """Return a done-callback that logs a failed awscrt future."""

    def _done(future: Future) -> None:
        if (err := future.exception()) is not None:
            _LOGGER.debug("MQTT %s failed: %s", action, err)

    return _done
