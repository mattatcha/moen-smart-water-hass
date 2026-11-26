"""Tests for wireless soil sensor devices and entities."""

from typing import Any
from unittest.mock import patch

import pytest
from homeassistant.const import (
    PERCENTAGE,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    EntityCategory,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.moen_smart_water_network.const import DOMAIN

CONTROLLER = "ctrl-0001"
CONNECTED = "soil-0001"
DISCONNECTED = "soil-0002"


def _entity_id(hass: HomeAssistant, platform: str, unique_id: str) -> str:
    """Return the entity id registered for a unique id."""
    entity_id = er.async_get(hass).async_get_entity_id(platform, DOMAIN, unique_id)
    assert entity_id is not None, f"no {platform} entity for {unique_id}"
    return entity_id


def _state(hass: HomeAssistant, platform: str, unique_id: str) -> Any:
    """Return the state object for a unique id."""
    state = hass.states.get(_entity_id(hass, platform, unique_id))
    assert state is not None
    return state


@pytest.mark.usefixtures("setup_irrigation")
async def test_soil_sensors_are_devices_connected_via_controller(
    hass: HomeAssistant,
) -> None:
    """Each soil sensor is its own device, reached through the controller."""
    registry = dr.async_get(hass)
    controller = registry.async_get_device(identifiers={(DOMAIN, CONTROLLER)})
    assert controller is not None

    sensor = registry.async_get_device(identifiers={(DOMAIN, CONNECTED)})
    assert sensor is not None
    assert sensor.via_device_id == controller.id
    assert sensor.name == "Front Yard"
    assert sensor.model == "Soil Sensor"
    assert sensor.model_id == "slsr"
    assert sensor.sw_version == "1"

    offline = registry.async_get_device(identifiers={(DOMAIN, DISCONNECTED)})
    assert offline is not None
    assert offline.via_device_id == controller.id
    # The device reports firmware "-1" while offline.
    assert offline.sw_version is None


@pytest.mark.usefixtures("setup_irrigation")
async def test_soil_sensor_readings(hass: HomeAssistant) -> None:
    """Moisture, temperature, battery, and last report are exposed."""
    depth1 = _state(hass, "sensor", f"{CONNECTED}_moisture_depth1")
    assert float(depth1.state) == pytest.approx(84.035156)
    assert depth1.attributes["unit_of_measurement"] == PERCENTAGE
    assert depth1.attributes["device_class"] == "moisture"
    assert depth1.attributes["linked_zone"] == "Front Yard"
    assert depth1.attributes["skip_threshold"] == 90

    depth3 = _state(hass, "sensor", f"{CONNECTED}_moisture_depth3")
    assert float(depth3.state) == pytest.approx(63.799576)
    assert depth3.attributes["skip_threshold"] == 80

    depth5 = _state(hass, "sensor", f"{CONNECTED}_moisture_depth5")
    assert float(depth5.state) == pytest.approx(52.030415)
    assert depth5.attributes["skip_threshold"] == 75

    temperature = _state(hass, "sensor", f"{CONNECTED}_soil_temperature")
    assert float(temperature.state) == 8
    assert temperature.attributes["unit_of_measurement"] == UnitOfTemperature.CELSIUS
    assert temperature.attributes["skip_threshold_celsius"] == 3

    battery = _state(hass, "sensor", f"{CONNECTED}_battery")
    assert battery.state == "100"

    last_report = _state(hass, "sensor", f"{CONNECTED}_last_report")
    assert last_report.state == "2026-11-26T20:53:06+00:00"

    assert _state(hass, "binary_sensor", f"{CONNECTED}_connected").state == STATE_ON


@pytest.mark.usefixtures("setup_irrigation")
async def test_soil_sensor_diagnostic_entities(hass: HomeAssistant) -> None:
    """Battery, signal, last report, and connected are diagnostic."""
    registry = er.async_get(hass)
    for platform, key in (
        ("sensor", "battery"),
        ("sensor", "signal_strength"),
        ("sensor", "last_report"),
        ("binary_sensor", "connected"),
    ):
        entry = registry.async_get(_entity_id(hass, platform, f"{CONNECTED}_{key}"))
        assert entry is not None
        assert entry.entity_category is EntityCategory.DIAGNOSTIC

    signal = registry.async_get(
        _entity_id(hass, "sensor", f"{CONNECTED}_signal_strength")
    )
    assert signal is not None
    assert signal.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.usefixtures("setup_irrigation")
async def test_disconnected_soil_sensor_hides_stale_readings(
    hass: HomeAssistant,
) -> None:
    """An offline sensor's readings are unavailable; its link state is not."""
    for key in ("moisture_depth1", "moisture_depth3", "moisture_depth5"):
        assert (
            _state(hass, "sensor", f"{DISCONNECTED}_{key}").state == STATE_UNAVAILABLE
        )
    assert (
        _state(hass, "sensor", f"{DISCONNECTED}_soil_temperature").state
        == STATE_UNAVAILABLE
    )

    assert _state(hass, "sensor", f"{DISCONNECTED}_battery").state == "40"
    assert (
        _state(hass, "sensor", f"{DISCONNECTED}_last_report").state
        == "2026-09-06T21:54:41+00:00"
    )
    assert _state(hass, "binary_sensor", f"{DISCONNECTED}_connected").state == STATE_OFF


async def test_removed_soil_sensor_becomes_unavailable(
    hass: HomeAssistant, setup_irrigation: Any
) -> None:
    """A soil sensor that drops out of the payload goes unavailable."""
    setup_irrigation.data["device"]["irrigation"]["soilSensors"] = []
    setup_irrigation.async_update_listeners()
    await hass.async_block_till_done()

    assert _state(hass, "sensor", f"{CONNECTED}_battery").state == STATE_UNAVAILABLE
    assert (
        _state(hass, "binary_sensor", f"{CONNECTED}_connected").state
        == STATE_UNAVAILABLE
    )


class TestControllerWithoutSoilSensors:
    """A controller with no soil sensors creates no soil sensor entities."""

    @pytest.fixture(name="irrigation_device")
    def irrigation_device_fixture(
        self, irrigation_device: dict[str, Any]
    ) -> dict[str, Any]:
        """Return the controller payload without the soil sensor add-ons."""
        irrigation_device["irrigation"].pop("soilSensors")
        return irrigation_device

    @pytest.mark.usefixtures("setup_irrigation")
    async def test_no_soil_sensor_entities(self, hass: HomeAssistant) -> None:
        """No soil sensor devices or entities are created."""
        registry = er.async_get(hass)
        assert (
            registry.async_get_entity_id("sensor", DOMAIN, f"{CONNECTED}_battery")
            is None
        )
        assert (
            dr.async_get(hass).async_get_device(identifiers={(DOMAIN, CONNECTED)})
            is None
        )


async def test_soil_sensor_device_info_uses_via_device_id(
    hass: HomeAssistant, setup_irrigation: Any
) -> None:
    """On Home Assistant releases with via_device_id, it replaces via_device."""
    controller = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, CONTROLLER)})
    assert controller is not None
    assert setup_irrigation.registry_device_id == controller.id

    entity = next(
        e for e in hass.data["sensor"].entities if e.unique_id == f"{CONNECTED}_battery"
    )
    with patch(
        "custom_components.moen_smart_water_network.entity.VIA_DEVICE_ID_SUPPORTED",
        new=True,
    ):
        info = entity.device_info
    assert info["via_device_id"] == controller.id
    assert "via_device" not in info

    with patch(
        "custom_components.moen_smart_water_network.entity.VIA_DEVICE_ID_SUPPORTED",
        new=False,
    ):
        info = entity.device_info
    assert info["via_device"] == (DOMAIN, CONTROLLER)
    assert "via_device_id" not in info
