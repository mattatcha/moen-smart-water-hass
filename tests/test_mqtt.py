"""Tests for the shared AWS IoT MQTT connection."""

import asyncio
from concurrent.futures import Future
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from awscrt import mqtt

from custom_components.moen_smart_water_network.moen_api import mqtt as moen_mqtt
from custom_components.moen_smart_water_network.moen_api.mqtt import (
    MoenMqttClient,
    _on_async_message,
)


def _done(result=None, error: Exception | None = None) -> Future:
    future: Future = Future()
    if error is not None:
        future.set_exception(error)
    else:
        future.set_result(result)
    return future


def _connection(*, connect_error: Exception | None = None) -> MagicMock:
    connection = MagicMock()
    connection.connect.return_value = _done(error=connect_error)
    connection.subscribe.return_value = (_done(), 1)
    connection.resubscribe_existing_topics.return_value = (_done(), 2)
    return connection


def _shadow_client() -> MagicMock:
    shadow = MagicMock()
    for name in (
        "subscribe_to_update_shadow_accepted",
        "subscribe_to_get_shadow_accepted",
        "subscribe_to_shadow_updated_events",
    ):
        getattr(shadow, name).return_value = (_done(), 1)
    shadow.publish_get_shadow.return_value = _done()
    return shadow


def _client() -> MoenMqttClient:
    auth = MagicMock()
    auth.async_ensure_token = AsyncMock()
    client = MoenMqttClient(auth=auth, legacy_id="legacy")
    client.add_device("thing-1", "duid-1", MagicMock(), MagicMock())
    client.add_device("thing-2", "duid-2", MagicMock())
    return client


def _signal_shadow_requests(shadow: MagicMock) -> asyncio.Event:
    """Return an event set once every device's shadow has been requested."""
    requested = asyncio.Event()

    def _publish(*_args: object, **_kwargs: object) -> Future:
        if shadow.publish_get_shadow.call_count == 2:  # one per device
            requested.set()
        return _done()

    shadow.publish_get_shadow.side_effect = _publish
    return requested


async def _wait(event: asyncio.Event) -> None:
    async with asyncio.timeout(5):
        await event.wait()


async def test_run_retries_until_connected_then_disconnects(monkeypatch) -> None:
    """A failed first connection is retried; one connection serves every device."""
    monkeypatch.setattr(moen_mqtt, "RETRY_MIN_SECONDS", 0)
    failing = _connection(connect_error=RuntimeError("handshake failed"))
    working = _connection()
    shadow = _shadow_client()
    requested = _signal_shadow_requests(shadow)
    client = _client()

    with (
        patch.object(
            moen_mqtt.mqtt_connection_builder,
            "websockets_with_default_aws_signing",
            side_effect=[failing, working],
        ) as build,
        patch.object(moen_mqtt.iotshadow, "IotShadowClient", return_value=shadow),
    ):
        task = asyncio.create_task(client.async_run())
        await _wait(requested)

        assert build.call_count == 2
        assert all(c.kwargs["clean_session"] for c in build.call_args_list)
        failing.disconnect.assert_called_once()
        assert shadow.subscribe_to_update_shadow_accepted.call_count == 2
        # Only the device with an async callback subscribes to /async/{duid}.
        working.subscribe.assert_called_once()
        assert working.subscribe.call_args.args[0] == "/async/duid-1"

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    working.disconnect.assert_called_once()


async def test_token_failure_is_retried(monkeypatch) -> None:
    """A token refresh failure doesn't end the MQTT task."""
    monkeypatch.setattr(moen_mqtt, "RETRY_MIN_SECONDS", 0)
    client = _client()
    client._auth.async_ensure_token.side_effect = [RuntimeError("offline"), None]
    shadow = _shadow_client()
    requested = _signal_shadow_requests(shadow)

    with (
        patch.object(
            moen_mqtt.mqtt_connection_builder,
            "websockets_with_default_aws_signing",
            return_value=_connection(),
        ) as build,
        patch.object(moen_mqtt.iotshadow, "IotShadowClient", return_value=shadow),
    ):
        task = asyncio.create_task(client.async_run())
        await _wait(requested)
        build.assert_called_once()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


@pytest.mark.parametrize(
    ("session_present", "resubscribed"), [(False, True), (True, False)]
)
def test_resume_restores_subscriptions_and_state(session_present, resubscribed) -> None:
    """After a reconnect, lost subscriptions are restored and shadows refetched."""
    client = _client()
    client._shadow_client = _shadow_client()
    connection = _connection()

    client._on_connection_resumed(
        connection, mqtt.ConnectReturnCode.ACCEPTED, session_present
    )

    assert connection.resubscribe_existing_topics.called is resubscribed
    assert client._shadow_client.publish_get_shadow.call_count == 2


def test_rejected_resume_does_nothing() -> None:
    """A rejected reconnect leaves awscrt to retry."""
    client = _client()
    client._shadow_client = _shadow_client()
    connection = _connection()

    client._on_connection_resumed(
        connection, mqtt.ConnectReturnCode.NOT_AUTHORIZED, session_present=False
    )

    connection.resubscribe_existing_topics.assert_not_called()
    client._shadow_client.publish_get_shadow.assert_not_called()


def test_async_message_decoding() -> None:
    """Valid JSON reaches the callback; invalid JSON is dropped."""
    callback = MagicMock()
    _on_async_message(callback, "/async/duid-1", b'{"event": "x"}')
    callback.assert_called_once_with({"event": "x"})

    callback.reset_mock()
    _on_async_message(callback, "/async/duid-1", b"not json")
    callback.assert_not_called()
