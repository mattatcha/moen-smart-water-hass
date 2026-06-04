"""Tests for the MoenDataUpdateCoordinator update flow."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.moen_smart_water_network.coordinator import (
    MoenDataUpdateCoordinator,
)
from custom_components.moen_smart_water_network.moen_api import (
    MoenApiAuthenticationError,
    MoenApiCommunicationError,
)

DEVICE_ID = "dev-1"
DEVICE_DATA = {"duid": DEVICE_ID, "clientId": "client-1"}
SCHEDULES = {"items": [{"id": "sched-1"}, {"id": "sched-2"}]}


def _build_coordinator(hass: HomeAssistant, config_entry) -> MoenDataUpdateCoordinator:
    """Build a coordinator with a mocked client and mqtt client."""
    client = MagicMock()
    client.async_user_presence = AsyncMock(return_value={})
    client.async_get_device = AsyncMock(return_value=DEVICE_DATA)
    client.async_get_schedules = AsyncMock(return_value=SCHEDULES)

    return MoenDataUpdateCoordinator(
        hass=hass,
        client=client,
        mqtt_client=MagicMock(),
        device_id=DEVICE_ID,
        data=DEVICE_DATA,
        legacy_id="123",
        config_entry=config_entry,
    )


async def test_presence_communication_failure_is_non_fatal(
    hass: HomeAssistant, config_entry
) -> None:
    """A 400 on the presence heartbeat must not fail the whole update."""
    coordinator = _build_coordinator(hass, config_entry)
    coordinator.client.async_user_presence.side_effect = MoenApiCommunicationError(
        "400, message='Bad Request'"
    )

    data = await coordinator._async_update_data()

    assert data["device"] == DEVICE_DATA
    assert set(data["schedules"]) == {"sched-1", "sched-2"}
    coordinator.client.async_get_device.assert_awaited_once_with(DEVICE_ID)


async def test_presence_auth_failure_is_non_fatal(
    hass: HomeAssistant, config_entry
) -> None:
    """A 401/403 on the presence heartbeat must not trigger reauth on its own."""
    coordinator = _build_coordinator(hass, config_entry)
    coordinator.client.async_user_presence.side_effect = MoenApiAuthenticationError(
        "Invalid credentials"
    )

    data = await coordinator._async_update_data()

    assert data["device"] == DEVICE_DATA


async def test_device_auth_failure_still_raises_reauth(
    hass: HomeAssistant, config_entry
) -> None:
    """A genuine auth failure fetching device data still triggers reauth."""
    coordinator = _build_coordinator(hass, config_entry)
    coordinator.client.async_get_device.side_effect = MoenApiAuthenticationError(
        "Invalid credentials"
    )

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_device_communication_failure_still_raises_update_failed(
    hass: HomeAssistant, config_entry
) -> None:
    """A communication failure fetching device data still fails the update."""
    coordinator = _build_coordinator(hass, config_entry)
    coordinator.client.async_get_device.side_effect = MoenApiCommunicationError(
        "boom"
    )

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
