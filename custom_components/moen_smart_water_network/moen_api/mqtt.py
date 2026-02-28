"""MQTT connection manager for Moen Smart Water Network."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from awscrt import io, mqtt
from awsiot import iotshadow, mqtt_connection_builder

from .const import ASYNC_TOPIC, MQTT_ENDPOINT, MQTT_REGION
from .exceptions import MoenApiError

if TYPE_CHECKING:
    from collections.abc import Callable

    from .auth import MoenAuth

_LOGGER = logging.getLogger(__name__)

io.init_logging(io.LogLevel.Warn, "stderr")


class MoenMqttClient:
    """MQTT client for shadow and async irrigation topic subscriptions."""

    def __init__(self, auth: MoenAuth) -> None:
        """Initialize with auth manager."""
        self._auth = auth
        self._mqtt_connection: mqtt.Connection | None = None
        self._shadow_client: iotshadow.IotShadowClient | None = None

    async def async_connect(
        self,
        client_id: str,
        duid: str,
        legacy_id: str,
        shadow_callback: Callable,
        async_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        """Connect to MQTT and subscribe to shadow + async topics."""
        credentials_provider = self._auth.create_cognito_credentials_provider(
            legacy_id
        )

        mqtt_client_id = str(uuid4())
        _LOGGER.debug("MQTT client id: %s", mqtt_client_id)

        loop = asyncio.get_running_loop()

        def _create_mqtt_connection() -> mqtt.Connection:
            return mqtt_connection_builder.websockets_with_default_aws_signing(
                region=MQTT_REGION,
                endpoint=MQTT_ENDPOINT,
                credentials_provider=credentials_provider,
                client_id=mqtt_client_id,
                clean_session=False,
                keep_alive_secs=30,
                on_connection_interrupted=lambda connection, error, **kwargs: (
                    _LOGGER.debug("MQTT connection interrupted: %s", error)
                ),
                on_connection_failure=lambda connection, callback_data, **kwargs: (
                    _LOGGER.error("MQTT connection failure: %s", callback_data)
                ),
                on_connection_resumed=lambda connection,
                return_code,
                session_present,
                **kwargs: (
                    _LOGGER.debug("MQTT connection resumed: %s", return_code)
                ),
                on_connection_success=lambda callback_data, **kwargs: (
                    _LOGGER.debug("MQTT connection success: %s", callback_data)
                ),
                on_connection_closed=lambda connection, callback_data, **kwargs: (
                    _LOGGER.debug("MQTT connection closed: %s", callback_data)
                ),
            )

        self._mqtt_connection = await loop.run_in_executor(
            None, _create_mqtt_connection
        )

        connected_future = self._mqtt_connection.connect()
        self._shadow_client = iotshadow.IotShadowClient(self._mqtt_connection)
        await loop.run_in_executor(None, connected_future.result)
        _LOGGER.debug("Connected to MQTT")

        # Subscribe to shadow topics
        await self._subscribe_shadow_topics(client_id, shadow_callback, loop)

        # Subscribe to /async/{duid} topic for irrigation run updates
        if async_callback is not None:
            await self._subscribe_async_topic(duid, async_callback, loop)

        # Request current shadow state
        await self._publish_get_shadow(client_id, loop)

        # Keep connection alive until cancelled
        disconnect_event = asyncio.Event()
        try:
            await disconnect_event.wait()
        except asyncio.CancelledError:
            _LOGGER.debug("MQTT subscription cancelled, disconnecting...")
            self._mqtt_connection.disconnect()
            raise

    async def async_disconnect(self) -> None:
        """Disconnect from MQTT."""
        if self._mqtt_connection is not None:
            self._mqtt_connection.disconnect()
            self._mqtt_connection = None
            self._shadow_client = None

    async def _subscribe_shadow_topics(
        self,
        client_id: str,
        callback: Callable,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        """Subscribe to all shadow topics for a device."""
        if self._shadow_client is None:
            raise MoenApiError("Shadow client not initialized")

        _LOGGER.debug("Subscribing to shadow update accepted...")
        update_future, _ = self._shadow_client.subscribe_to_update_shadow_accepted(
            request=iotshadow.UpdateShadowSubscriptionRequest(thing_name=client_id),
            qos=mqtt.QoS.AT_LEAST_ONCE,
            callback=callback,
        )
        await loop.run_in_executor(None, update_future.result)

        _LOGGER.debug("Subscribing to shadow get accepted...")
        get_future, _ = self._shadow_client.subscribe_to_get_shadow_accepted(
            request=iotshadow.GetShadowSubscriptionRequest(thing_name=client_id),
            qos=mqtt.QoS.AT_LEAST_ONCE,
            callback=callback,
        )
        await loop.run_in_executor(None, get_future.result)

        _LOGGER.debug("Subscribing to shadow updated events...")
        events_future, _ = self._shadow_client.subscribe_to_shadow_updated_events(
            request=iotshadow.ShadowUpdatedSubscriptionRequest(thing_name=client_id),
            qos=mqtt.QoS.AT_LEAST_ONCE,
            callback=callback,
        )
        await loop.run_in_executor(None, events_future.result)

    async def _subscribe_async_topic(
        self,
        duid: str,
        callback: Callable[[dict[str, Any]], None],
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        """Subscribe to the /async/{duid} topic for real-time irrigation updates."""
        if self._mqtt_connection is None:
            raise MoenApiError("MQTT connection not established")

        topic = ASYNC_TOPIC.format(duid=duid)
        _LOGGER.debug("Subscribing to async topic: %s", topic)

        def _on_message(topic: str, payload: bytes, **_: Any) -> None:
            try:
                message = json.loads(payload)
                _LOGGER.debug("Received async message on %s: %s", topic, message)
                callback(message)
            except Exception:
                _LOGGER.exception("Failed to parse async MQTT message")

        subscribe_future, _ = self._mqtt_connection.subscribe(
            topic=topic,
            qos=mqtt.QoS.AT_LEAST_ONCE,
            callback=_on_message,
        )
        await loop.run_in_executor(None, subscribe_future.result)
        _LOGGER.debug("Subscribed to async topic: %s", topic)

    async def _publish_get_shadow(
        self,
        client_id: str,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        """Publish a get shadow request to receive current state."""
        if self._shadow_client is None:
            raise MoenApiError("Shadow client not initialized")

        publish_future = self._shadow_client.publish_get_shadow(
            request=iotshadow.GetShadowRequest(thing_name=client_id),
            qos=mqtt.QoS.AT_LEAST_ONCE,
        )
        await loop.run_in_executor(None, publish_future.result)
