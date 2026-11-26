"""Calendar platform for moen_smart_water_network."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import MoenDataUpdateCoordinator, schedule_run_window
from .entity import MoenEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .moen_api.models import ScheduleData

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the calendar platform."""
    devices: list[MoenDataUpdateCoordinator] = hass.data[DOMAIN][config_entry.entry_id][
        "devices"
    ]

    entities = [IrrigationCalendar(device) for device in devices]
    async_add_entities(entities)


def _events_for_schedule(
    schedule: ScheduleData,
    start_date: datetime,
    end_date: datetime,
) -> list[CalendarEvent]:
    """Generate the events of a schedule that overlap a date range."""
    if schedule.get("status") != "active":
        return []

    events: list[CalendarEvent] = []
    # Start a day early: a run anchored on one day can overlap the range from
    # the day before (and an endBefore run can start the previous evening).
    current = (start_date - timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    last_day = end_date + timedelta(days=1)

    while current <= last_day:
        if MoenDataUpdateCoordinator.matches_schedule_day(current, schedule):
            window = schedule_run_window(schedule, current)
            if window is None:
                return []
            event_start, event_end = window
            if event_end > start_date and event_start < end_date:
                events.append(
                    CalendarEvent(
                        summary=schedule.get("name", "Irrigation"),
                        start=event_start,
                        end=event_end,
                    )
                )
        current += timedelta(days=1)

    return events


class IrrigationCalendar(MoenEntity, CalendarEntity):
    """Read-only calendar showing irrigation schedules."""

    _attr_icon = "mdi:sprinkler"

    @property
    def unique_id(self) -> str:
        """Return a unique id."""
        return f"{self._device.id}_irrigation_calendar"

    @property
    def name(self) -> str:
        """Return the friendly name."""
        return "Irrigation Calendar"

    @property
    def event(self) -> CalendarEvent | None:
        """Return the active event, or the next upcoming one."""
        now = dt_util.now()
        end = now + timedelta(days=15)

        next_event: CalendarEvent | None = None
        schedules: dict[str, ScheduleData] = self._device.data.get("schedules", {})

        for schedule in schedules.values():
            events = _events_for_schedule(schedule, now, end)
            for ev in events:
                if next_event is None or ev.start < next_event.start:
                    next_event = ev

        return next_event

    async def async_get_events(
        self,
        hass: HomeAssistant,  # noqa: ARG002
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events within a date range."""
        schedules: dict[str, ScheduleData] = self._device.data.get("schedules", {})
        events: list[CalendarEvent] = []

        for schedule in schedules.values():
            events.extend(_events_for_schedule(schedule, start_date, end_date))

        events.sort(key=lambda e: e.start)
        return events
