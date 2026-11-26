"""Tests for controller and zone status entities and schedule timing."""

from datetime import datetime, timedelta
from typing import Any

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import (
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityCategory,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    mock_restore_cache_with_extra_data,
)

from custom_components.moen_smart_water_network.calendar import (
    _events_for_schedule,
)
from custom_components.moen_smart_water_network.const import DOMAIN
from custom_components.moen_smart_water_network.coordinator import (
    schedule_run_window,
)

CONTROLLER = "ctrl-0001"


def _entity_id(hass: HomeAssistant, platform: str, unique_id: str) -> str:
    """Return the entity id registered for a unique id."""
    entity_id = er.async_get(hass).async_get_entity_id(platform, DOMAIN, unique_id)
    assert entity_id is not None, f"no {platform} entity for {unique_id}"
    return entity_id


def _state(hass: HomeAssistant, platform: str, unique_id: str) -> State:
    """Return the state object for a unique id."""
    state = hass.states.get(_entity_id(hass, platform, unique_id))
    assert state is not None
    return state


async def _shadow(hass: HomeAssistant, coordinator: Any, hydra: dict) -> None:
    """Apply a hydraOverview shadow update."""
    coordinator._apply_shadow_update({"hydraOverview": hydra})
    await hass.async_block_till_done()


# --- Rain sensor ---


async def test_rain_sensor_reports_rain_not_connectivity(
    hass: HomeAssistant, setup_irrigation: Any
) -> None:
    """The rain sensor shows dry/wet from the shadow, not whether it's wired."""
    rain = f"{CONTROLLER}_rain_sensor"
    # No shadow yet: unknown rather than a misleading "wet".
    assert _state(hass, "binary_sensor", rain).state == STATE_UNKNOWN

    await _shadow(hass, setup_irrigation, {"rain": "dry"})
    state = _state(hass, "binary_sensor", rain)
    assert state.state == STATE_OFF
    assert state.attributes["rain_state"] == "dry"
    assert state.attributes["device_class"] == "moisture"

    await _shadow(hass, setup_irrigation, {"rain": "wet"})
    assert _state(hass, "binary_sensor", rain).state == STATE_ON

    connected = _state(hass, "binary_sensor", f"{CONTROLLER}_rain_sensor_connected")
    assert connected.state == STATE_ON
    assert connected.attributes["device_class"] == "connectivity"


class TestRainSensorDisconnected:
    """Rain state is unavailable when no rain sensor is connected."""

    @pytest.fixture(name="irrigation_device")
    def irrigation_device_fixture(
        self, irrigation_device: dict[str, Any]
    ) -> dict[str, Any]:
        """Return a controller without a connected rain sensor."""
        irrigation_device["irrigation"]["rainSensor"]["connected"] = False
        return irrigation_device

    async def test_rain_unavailable(
        self, hass: HomeAssistant, setup_irrigation: Any
    ) -> None:
        """The rain entity is unavailable; the connectivity entity is off."""
        await _shadow(hass, setup_irrigation, {"rain": "dry"})
        assert (
            _state(hass, "binary_sensor", f"{CONTROLLER}_rain_sensor").state
            == STATE_UNAVAILABLE
        )
        assert (
            _state(hass, "binary_sensor", f"{CONTROLLER}_rain_sensor_connected").state
            == STATE_OFF
        )


@pytest.mark.usefixtures("setup_irrigation")
async def test_connectivity_sensors_are_diagnostic(hass: HomeAssistant) -> None:
    """Master valve and rain sensor connectivity are diagnostic entities."""
    registry = er.async_get(hass)
    for key in ("master_valve", "rain_sensor_connected", "flow_sensor"):
        entry = registry.async_get(
            _entity_id(hass, "binary_sensor", f"{CONTROLLER}_{key}")
        )
        assert entry is not None
        assert entry.entity_category is EntityCategory.DIAGNOSTIC


# --- Controller status ---


async def test_watering_restricted(hass: HomeAssistant, setup_irrigation: Any) -> None:
    """Watering restricted follows the shadow's restricted flag."""
    restricted = f"{CONTROLLER}_watering_restricted"
    assert _state(hass, "binary_sensor", restricted).state == STATE_UNKNOWN

    await _shadow(hass, setup_irrigation, {"restricted": False})
    assert _state(hass, "binary_sensor", restricted).state == STATE_OFF

    await _shadow(hass, setup_irrigation, {"restricted": True})
    assert _state(hass, "binary_sensor", restricted).state == STATE_ON


@pytest.mark.usefixtures("setup_irrigation")
async def test_active_alerts(hass: HomeAssistant) -> None:
    """Only active alerts are counted, broken down by severity."""
    state = _state(hass, "sensor", f"{CONTROLLER}_active_alerts")
    assert state.state == "1"
    assert state.attributes["warning"] == 1
    assert "critical" not in state.attributes


@pytest.mark.usefixtures("setup_irrigation")
async def test_seasonal_adjustment(hass: HomeAssistant) -> None:
    """Seasonal adjustment shows the current month's percentage."""
    state = _state(hass, "sensor", f"{CONTROLLER}_seasonal_adjustment")
    assert state.state == str(dt_util.now().month * 10)
    assert state.attributes["unit_of_measurement"] == "%"


# --- Zones ---


@pytest.mark.usefixtures("setup_irrigation")
async def test_zone_fault(hass: HomeAssistant) -> None:
    """Wired zones report faults; unwired zones get no entity."""
    healthy = _state(hass, "binary_sensor", f"{CONTROLLER}_zone_1_fault")
    assert healthy.state == STATE_OFF
    assert healthy.attributes["audit_status"] == "normal"

    faulted = _state(hass, "binary_sensor", f"{CONTROLLER}_zone_2_fault")
    assert faulted.state == STATE_ON
    assert faulted.attributes["fault"] == "current_low"
    assert faulted.attributes["device_class"] == "problem"

    registry = er.async_get(hass)
    assert (
        registry.async_get_entity_id(
            "binary_sensor", DOMAIN, f"{CONTROLLER}_zone_8_fault"
        )
        is None
    )


def _run_message(completed: list[dict[str, Any]]) -> dict[str, Any]:
    """Build an irrigation_run_update message."""
    return {
        "event": "irrigation_run_update",
        "ts": 1795000000000,
        "body": {
            "id": "run-1",
            "state": {"status": "COMPLETED", "completed": completed},
        },
    }


async def test_zone_last_watered(hass: HomeAssistant, setup_irrigation: Any) -> None:
    """Completed zones record when they finished; skipped ones don't."""
    zone1 = f"{CONTROLLER}_zone_1_last_watered"
    zone2 = f"{CONTROLLER}_zone_2_last_watered"
    assert _state(hass, "sensor", zone1).state == STATE_UNKNOWN

    finished = datetime(2026, 11, 20, 6, 0, tzinfo=dt_util.UTC)
    setup_irrigation._apply_irrigation_run(
        _run_message(
            [
                # Client id with a millisecond timestamp.
                {
                    "zoneId": "1",
                    "status": "COMPLETED",
                    "ts": int(finished.timestamp() * 1000),
                    "actualDuration": 600,
                },
                # Full zone id, skipped: not watered.
                {
                    "zoneId": f"{CONTROLLER}_2",
                    "status": "SKIPPED",
                    "ts": int(finished.timestamp()),
                    "actualDuration": 0,
                },
            ]
        )
    )
    await hass.async_block_till_done()

    assert dt_util.parse_datetime(_state(hass, "sensor", zone1).state) == finished
    assert _state(hass, "sensor", zone2).state == STATE_UNKNOWN

    # Full zone id with a second-resolution timestamp.
    later = finished + timedelta(days=1)
    setup_irrigation._apply_irrigation_run(
        _run_message(
            [
                {
                    "zoneId": f"{CONTROLLER}_2",
                    "status": "COMPLETED",
                    "ts": int(later.timestamp()),
                    "actualDuration": 300,
                }
            ]
        )
    )
    await hass.async_block_till_done()
    assert dt_util.parse_datetime(_state(hass, "sensor", zone2).state) == later


RESTORED_ZONE_ENTITY = "sensor.smart_sprinkler_controller_front_yard_last_watered"


class TestZoneLastWateredRestore:
    """The last watered time survives a restart."""

    @pytest.fixture(autouse=True)
    def restore_cache(self, hass: HomeAssistant) -> None:
        """Prime the restore cache before the integration is set up."""
        mock_restore_cache_with_extra_data(
            hass,
            (
                (
                    State(RESTORED_ZONE_ENTITY, "2026-11-01T06:00:00+00:00"),
                    {
                        "native_value": {
                            "__type": "<class 'datetime.datetime'>",
                            "isoformat": "2026-11-01T06:00:00+00:00",
                        },
                        "native_unit_of_measurement": None,
                    },
                ),
            ),
        )

    @pytest.mark.usefixtures("setup_irrigation")
    async def test_restored(self, hass: HomeAssistant) -> None:
        """The restored value is shown after a restart."""
        zone1 = _entity_id(hass, "sensor", f"{CONTROLLER}_zone_1_last_watered")
        assert zone1 == RESTORED_ZONE_ENTITY
        state = hass.states.get(zone1)
        assert state is not None
        assert state.state == "2026-11-01T06:00:00+00:00"


# --- Schedule timing ---

LOCAL_DAY = datetime(2026, 11, 28, tzinfo=dt_util.get_default_time_zone())


def test_start_at_window_uses_seconds() -> None:
    """Zone durations are seconds: 4 x 120 s is an 8 minute run."""
    schedule = {
        "preferredTime": {"startAt": "05:52:00"},
        "zones": [{"duration": 120}] * 4,
    }
    window = schedule_run_window(schedule, LOCAL_DAY)
    assert window is not None
    start, end = window
    assert (start.hour, start.minute) == (5, 52)
    assert end - start == timedelta(minutes=8)


def test_end_before_window_ends_on_time() -> None:
    """An endBefore schedule ends at its deadline and starts that much earlier."""
    schedule = {
        "preferredTime": {"endBefore": "05:50:00"},
        "zones": [{"duration": 4200}, {"duration": 4200}, {"duration": 3000}],
    }
    window = schedule_run_window(schedule, LOCAL_DAY)
    assert window is not None
    start, end = window
    assert (end.hour, end.minute) == (5, 50)
    assert end - start == timedelta(seconds=11400)


def test_schedule_without_time_has_no_window() -> None:
    """A schedule with neither startAt nor endBefore has no window."""
    assert schedule_run_window({"preferredTime": {}, "zones": []}, LOCAL_DAY) is None


END_BEFORE_SCHEDULE = {
    "id": "sched-lawn",
    "name": "Lawn Hydrate",
    "status": "active",
    "frequency": "weekly",
    "daysOfWeek": ["saturday"],
    "preferredTime": {"endBefore": "05:50:00"},
    "zones": [{"duration": 3600, "clientId": 1}, {"duration": 3600, "clientId": 2}],
}


def test_calendar_includes_end_before_schedules() -> None:
    """Calendar events are generated for endBefore schedules."""
    tz = dt_util.get_default_time_zone()
    start = datetime(2026, 11, 22, tzinfo=tz)
    end = datetime(2026, 12, 6, tzinfo=tz)

    events = _events_for_schedule(END_BEFORE_SCHEDULE, start, end)

    assert [event.start for event in events] == [
        datetime(2026, 11, 28, 3, 50, tzinfo=tz),
        datetime(2026, 12, 5, 3, 50, tzinfo=tz),
    ]
    assert all(event.end - event.start == timedelta(hours=2) for event in events)


def test_calendar_includes_running_event() -> None:
    """An event that started before the range but is still running overlaps it."""
    tz = dt_util.get_default_time_zone()
    start = datetime(2026, 11, 28, 4, 0, tzinfo=tz)
    end = datetime(2026, 11, 28, 5, 0, tzinfo=tz)

    events = _events_for_schedule(END_BEFORE_SCHEDULE, start, end)

    assert [event.start for event in events] == [
        datetime(2026, 11, 28, 3, 50, tzinfo=tz)
    ]


class TestNextScheduleRun:
    """Next Schedule Run covers endBefore schedules."""

    @pytest.fixture(name="irrigation_schedules")
    def irrigation_schedules_fixture(self) -> dict[str, Any]:
        """Return one active endBefore schedule."""
        return {"items": [END_BEFORE_SCHEDULE], "total": 1, "params": {}}

    async def test_next_run(
        self, freezer: FrozenDateTimeFactory, setup_irrigation: Any
    ) -> None:
        """The next run is the estimated start of the endBefore schedule."""
        tz = dt_util.get_default_time_zone()
        freezer.move_to(datetime(2026, 11, 25, 12, 0, tzinfo=tz))

        assert setup_irrigation.next_schedule_run == datetime(
            2026, 11, 28, 3, 50, tzinfo=tz
        )
