"""Test sprinkler controller sensors."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.moen_smart_water_network.const import DOMAIN

from .conftest import IRRIGATION_DUID, FakeMoenCloud


async def test_sensors(
    hass: HomeAssistant, config_entry, moen_cloud: FakeMoenCloud
) -> None:
    """Sprinkler sensors are created and read the device data."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{IRRIGATION_DUID}_watering_mode"
    )
    assert entity_id is not None
    assert hass.states.get(entity_id).state == "off"

    rssi = registry.async_get_entity_id("sensor", DOMAIN, f"{IRRIGATION_DUID}_rssi")
    assert hass.states.get(rssi).state == "-40"

    assert await hass.config_entries.async_unload(config_entry.entry_id)
