"""Tests for the zone valve entity and the start_watering service."""

from unittest.mock import AsyncMock, MagicMock

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.moen_smart_water_network.const import (
    CLIENT,
    CONF_ZONE_DURATIONS,
    DOMAIN,
)
from custom_components.moen_smart_water_network.valve import ZoneValve

ZONE = {"id": "dev-1_3", "clientId": 3, "name": "Front Lawn"}


def _build_valve(durations: dict[str, int]) -> tuple[ZoneValve, MagicMock]:
    """Build a valve for ZONE with a mocked device and config entry."""
    device = MagicMock()
    device.id = "dev-1"
    device.client.async_create_manual_plan = AsyncMock()
    device.async_request_refresh = AsyncMock()
    config_entry = MagicMock()
    config_entry.options = {CONF_ZONE_DURATIONS: durations}
    return ZoneValve(device, ZONE, config_entry), device


async def test_open_valve_sends_duration_in_seconds() -> None:
    """Opening the valve converts the configured minutes to seconds."""
    valve, device = _build_valve({"3": 7})

    await valve.async_open_valve()

    device.client.async_create_manual_plan.assert_awaited_once_with(
        device_id="dev-1",
        name="Home Assistant Manual Run",
        zones=[{"id": "dev-1_3", "duration": 420}],
    )


async def test_start_watering_service_sends_duration_in_seconds(
    hass: HomeAssistant,
) -> None:
    """The start_watering service converts its minutes field to seconds."""
    assert await async_setup_component(hass, DOMAIN, {})
    client = MagicMock()
    client.async_create_manual_plan = AsyncMock()
    hass.data[DOMAIN]["entry-1"] = {CLIENT: client}

    await hass.services.async_call(
        DOMAIN,
        "start_watering",
        {"device_id": "dev-1", "zone_id": "3", "duration": 10},
        blocking=True,
    )

    client.async_create_manual_plan.assert_awaited_once_with(
        device_id="dev-1",
        name="Home Assistant Manual Run",
        zones=[{"id": "dev-1_3", "duration": 600}],
    )
