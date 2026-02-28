"""Test sensors."""

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.moen_smart_water_network import (
    CONF_ACCESS_TOKEN,
    CONF_REFRESH_TOKEN,
    DOMAIN,
)
from custom_components.moen_smart_water_network.moen_api.const import API_USER_URL


async def test_sensors(
    hass: HomeAssistant,
    config_entry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test moen sensors"""
    config_entry.add_to_hass(hass)
    aioclient_mock.get(
        "https://api.prod.iot.moen.com/v3/devices",
        status=200,
        json={
            "devices": [{"duid": "a", "clientId": "1"}, {"duid": "b", "clientId": "2"}]
        },
    )
    aioclient_mock.get(
        API_USER_URL,
        status=200,
        json={"resp": {"a": "123"}},
    )

    assert await async_setup_component(
        hass, DOMAIN, {CONF_ACCESS_TOKEN: "a", CONF_REFRESH_TOKEN: "b"}
    )
    await hass.async_block_till_done()
    assert len(hass.data[DOMAIN][config_entry.entry_id]["devices"]) == 2

    # assert hass.states == "home"
    # assert hass.states.get("sensor.smart_sprinkler_controller_2").state == "home"

    assert await hass.config_entries.async_unload(config_entry.entry_id)
