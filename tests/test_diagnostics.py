"""Tests for the diagnostics download."""

from typing import Any

from homeassistant.core import HomeAssistant

from custom_components.moen_smart_water_network.diagnostics import (
    async_get_config_entry_diagnostics,
)


async def test_diagnostics_include_soil_sensors(
    hass: HomeAssistant, config_entry: Any, setup_irrigation: Any
) -> None:
    """Diagnostics carry the per-device payload, which includes soil sensors."""
    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)

    controller = diagnostics["coordinators"][setup_irrigation.id]
    device = controller["device"]
    assert len(device["irrigation"]["soilSensors"]) == 2
