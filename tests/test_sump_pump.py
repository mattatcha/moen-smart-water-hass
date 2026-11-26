"""Tests for multi-device setup and the sump pump monitor (type "nab")."""

from datetime import timedelta

import pytest
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.moen_smart_water_network import (
    async_remove_config_entry_device,
)
from custom_components.moen_smart_water_network.const import DOMAIN
from custom_components.moen_smart_water_network.moen_api import MoenApiError
from custom_components.moen_smart_water_network.moen_api.client import (
    unwrap_invoker_response,
)

from .conftest import (
    FLO_DUIDS,
    IRRIGATION_CLIENT_ID,
    IRRIGATION_DUID,
    SUMP_PUMP_CLIENT_ID,
    SUMP_PUMP_DUID,
    FakeMoenCloud,
)


async def _setup(hass: HomeAssistant, config_entry) -> None:
    hass.config.units = US_CUSTOMARY_SYSTEM
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


def _entity_id(hass: HomeAssistant, platform: str, unique_id: str) -> str | None:
    return er.async_get(hass).async_get_entity_id(platform, DOMAIN, unique_id)


def _state(
    hass: HomeAssistant, platform: str, key: str, duid: str = SUMP_PUMP_DUID
) -> State:
    entity_id = _entity_id(hass, platform, f"{duid}_{key}")
    assert entity_id is not None, f"{platform} {key} not registered"
    state = hass.states.get(entity_id)
    assert state is not None
    return state


async def test_setup_skips_flo_and_splits_device_types(
    hass: HomeAssistant, config_entry, moen_cloud: FakeMoenCloud
) -> None:
    """Flo valves are skipped; irrigation entities exist only on the sprinkler."""
    await _setup(hass, config_entry)

    devices = dr.async_entries_for_config_entry(
        dr.async_get(hass), config_entry.entry_id
    )
    duids = {i[1] for device in devices for i in device.identifiers}
    assert duids == {SUMP_PUMP_DUID, IRRIGATION_DUID}
    assert not duids & set(FLO_DUIDS)

    # Zone controls exist for the wired sprinkler zone only.
    assert _entity_id(hass, "valve", f"{IRRIGATION_DUID}_zone_1_valve")
    assert _entity_id(hass, "switch", f"{IRRIGATION_DUID}_zone_1")
    assert _entity_id(hass, "number", f"{IRRIGATION_DUID}_zone_1_duration")
    assert _entity_id(hass, "valve", f"{IRRIGATION_DUID}_zone_8_valve") is None

    # No irrigation entities on the sump pump.
    for platform, key in (
        ("binary_sensor", "watering"),
        ("binary_sensor", "rain_sensor"),
        ("calendar", "irrigation_calendar"),
        ("sensor", "watering_mode"),
        ("sensor", "running_zone"),
    ):
        assert _entity_id(hass, platform, f"{SUMP_PUMP_DUID}_{key}") is None

    assert await hass.config_entries.async_unload(config_entry.entry_id)


async def test_devices_share_one_mqtt_connection(
    hass: HomeAssistant, config_entry, moen_cloud: FakeMoenCloud, mock_mqtt
) -> None:
    """Every device subscribes on one MQTT client, stopped on unload."""
    await _setup(hass, config_entry)

    mock_mqtt.assert_called_once()
    instance = mock_mqtt.return_value
    thing_names = {c.args[0] for c in instance.add_device.call_args_list}
    assert thing_names == {SUMP_PUMP_CLIENT_ID, IRRIGATION_CLIENT_ID}
    instance.async_run.assert_awaited_once()

    assert await hass.config_entries.async_unload(config_entry.entry_id)


async def test_sump_pump_values_match_api(
    hass: HomeAssistant, config_entry, moen_cloud: FakeMoenCloud
) -> None:
    """Sensor values come from the captured API responses."""
    await _setup(hass, config_entry)

    assert _state(hass, "sensor", "temperature").state == "74"
    assert _state(hass, "sensor", "humidity").state == "27"
    assert _state(hass, "sensor", "battery").state == "90"
    assert _state(hass, "sensor", "rssi").state == "-55"
    assert _state(hass, "sensor", "last_cycle_volume").state == "3.77"
    assert _state(hass, "sensor", "last_cycle_run_time").state == "33.4"
    # 3.77 gal in 33.38 s; the app shows "6.8 gpm"
    assert _state(hass, "sensor", "last_cycle_pump_out_rate").state == "6.78"
    assert _state(hass, "sensor", "last_cycle_inflow_rate").state == "0"
    fill = float(_state(hass, "sensor", "last_cycle_fill_time").state)
    assert fill == pytest.approx(788563 / 3600, abs=0.01)
    last = _state(hass, "sensor", "last_pump_cycle")
    assert last.state == "2026-11-05T08:38:38+00:00"
    assert last.attributes["backup_used"] is False
    capacity = _state(hass, "sensor", "primary_pump_capacity")
    assert capacity.state == "undersized_capacity"
    assert capacity.attributes["pump_capacity_sufficient"] is False
    assert capacity.attributes["highest_capacity_days"][0]["capacity"] == 97
    assert _state(hass, "sensor", "primary_pump_peak_capacity").state == "97"
    backup_test = _state(hass, "sensor", "backup_pump_test")
    assert backup_test.state == "none"
    assert backup_test.attributes["last_result_time"] is None
    settings = _state(hass, "sensor", "alert_settings")
    assert settings.state == "normal"
    assert settings.attributes["temperature_high_threshold"] == 149.9
    assert settings.attributes["beeper_siren_enabled"] is True
    assert _state(hass, "sensor", "active_alerts").state == "0"

    assert _state(hass, "binary_sensor", "connected").state == STATE_ON
    assert _state(hass, "binary_sensor", "ac_power").state == STATE_ON
    assert _state(hass, "binary_sensor", "water_detected").state == STATE_OFF

    firmware = _state(hass, "update", "firmware")
    assert firmware.state == STATE_OFF
    assert firmware.attributes["installed_version"] == "v1.0.8w"

    assert await hass.config_entries.async_unload(config_entry.entry_id)


async def test_droplet_unknown_until_streaming(
    hass: HomeAssistant, config_entry, moen_cloud: FakeMoenCloud
) -> None:
    """Water level fields are unknown until the device streams, then populate."""
    await _setup(hass, config_entry)

    assert _state(hass, "sensor", "flood_risk").state == STATE_UNKNOWN
    assert _state(hass, "sensor", "primary_pump_state").state == STATE_UNKNOWN

    moen_cloud.set_droplet(
        level=3,
        trend="stable",
        floodRisk="normal",
        primaryState="operational",
        backupState="operational",
    )
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=61))
    await hass.async_block_till_done()

    assert _state(hass, "sensor", "flood_risk").state == "normal"
    assert _state(hass, "sensor", "water_level_trend").state == "stable"
    assert _state(hass, "sensor", "primary_pump_state").state == "operational"
    assert _state(hass, "sensor", "backup_pump_state").state == "operational"

    assert await hass.config_entries.async_unload(config_entry.entry_id)


async def test_streaming_requested_only_when_stopped(
    hass: HomeAssistant, config_entry, moen_cloud: FakeMoenCloud, freezer
) -> None:
    """drop_on is sent when streaming is off, not while on; updates_off on unload."""
    streaming = {
        "level": 3,
        "trend": "stable",
        "floodRisk": "normal",
        "primaryState": "operational",
        "backupState": "operational",
    }
    not_streaming = {
        "level": -1,
        "trend": "stable",
        "floodRisk": "unknown",
        "primaryState": "unknown",
        "backupState": "unknown",
    }
    await _setup(hass, config_entry)
    assert moen_cloud.commands() == ["drop_on"]
    assert all(
        body["clientId"] == SUMP_PUMP_CLIENT_ID
        for fn, body in moen_cloud.invocations
        if fn == "smartwater-app-shadow-api-prod-update"
    )

    # Streaming: no further requests.
    moen_cloud.set_droplet(**streaming)
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert moen_cloud.commands() == ["drop_on"]

    # Something else (e.g. the app closing) stopped streaming: request again.
    moen_cloud.set_droplet(**not_streaming)
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert moen_cloud.commands() == ["drop_on", "drop_on"]

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert moen_cloud.commands() == ["drop_on", "drop_on", "updates_off"]


async def test_alerts_filtered_to_device(
    hass: HomeAssistant, config_entry, moen_cloud: FakeMoenCloud
) -> None:
    """Only this device's alerts count; alert 250 turns on water detected."""
    moen_cloud.alerts = [
        {
            "id": "250",
            "duid": SUMP_PUMP_CLIENT_ID,
            "state": "active_unlack_unrack_unsuppressed",
            "severity": "critical",
            "title": "Water Detected",
            "time": "2026-11-25T00:00:00.000Z",
        },
        {
            "id": "2350",
            "duid": "100000002",
            "state": "active_unlack_unrack_unsuppressed",
            "severity": "warning",
            "title": "Soil Sensor Communication Lost",
        },
    ]
    await _setup(hass, config_entry)

    assert _state(hass, "binary_sensor", "water_detected").state == STATE_ON
    alerts = _state(hass, "sensor", "active_alerts")
    assert alerts.state == "1"
    assert alerts.attributes["alerts"][0]["title"] == "Water Detected"

    assert await hass.config_entries.async_unload(config_entry.entry_id)


async def test_failing_slow_endpoint_keeps_device_available(
    hass: HomeAssistant, config_entry, moen_cloud: FakeMoenCloud
) -> None:
    """A Lambda error on one endpoint leaves the rest of the device working."""
    moen_cloud.failing.add("fbgpg_usage_v1_get_device_environment_latest_prod")
    await _setup(hass, config_entry)

    assert _state(hass, "sensor", "temperature").state == STATE_UNKNOWN
    assert _state(hass, "sensor", "battery").state == "90"

    assert await hass.config_entries.async_unload(config_entry.entry_id)


async def test_firmware_for_every_device_unknown_on_failure(
    hass: HomeAssistant, config_entry, moen_cloud: FakeMoenCloud
) -> None:
    """Every device gets a firmware entity; a failed check shows unknown."""
    moen_cloud.failing.add("fbgpg_device_v1_device_get_latest_firmware_prod")
    await _setup(hass, config_entry)

    for duid in (SUMP_PUMP_DUID, IRRIGATION_DUID):
        firmware = _state(hass, "update", "firmware", duid)
        assert firmware.state == STATE_UNKNOWN
        assert firmware.attributes["latest_version"] is None

    assert await hass.config_entries.async_unload(config_entry.entry_id)


async def test_remove_config_entry_device(
    hass: HomeAssistant, config_entry, moen_cloud: FakeMoenCloud
) -> None:
    """Only devices the Moen account no longer reports can be deleted."""
    await _setup(hass, config_entry)
    registry = dr.async_get(hass)
    current = registry.async_get_device(identifiers={(DOMAIN, SUMP_PUMP_DUID)})
    assert current is not None
    stale = registry.async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={(DOMAIN, "gone-duid")}
    )

    assert not await async_remove_config_entry_device(hass, config_entry, current)
    assert await async_remove_config_entry_device(hass, config_entry, stale)

    assert await hass.config_entries.async_unload(config_entry.entry_id)


def test_unwrap_invoker_response_shapes() -> None:
    """Invoker payloads are unwrapped; Lambda errors raise."""
    fn = "fn"
    wrapped = {"StatusCode": 200, "Payload": {"statusCode": 200, "body": '{"a": 1}'}}
    assert unwrap_invoker_response(fn, wrapped) == {"a": 1}
    assert unwrap_invoker_response(fn, {"Payload": '{"usage": []}'}) == {"usage": []}
    assert unwrap_invoker_response(fn, {"Payload": {"status": True}}) == {
        "status": True
    }
    with pytest.raises(MoenApiError):
        unwrap_invoker_response(
            fn, {"Payload": {"errorType": "DatabaseException", "errorMessage": "x"}}
        )
    with pytest.raises(MoenApiError):
        unwrap_invoker_response(fn, {"Payload": {"statusCode": 502, "body": "bad"}})
