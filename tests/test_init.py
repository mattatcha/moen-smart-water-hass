"""Test init."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import FakeMoenCloud


async def test_setup_and_unload_entry(
    hass: HomeAssistant, config_entry, moen_cloud: FakeMoenCloud
) -> None:
    """The entry loads with Flo, sump pump and sprinkler devices, and unloads."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED
