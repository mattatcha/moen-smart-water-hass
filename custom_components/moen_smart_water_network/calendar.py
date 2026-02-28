"""Calendar platform for moen_smart_water_network."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import MoenDataUpdateCoordinator
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


def _parse_start_time(start_at: str) -> tuple[int, int] | None:
    """Parse a HH:MM time string into (hour, minute)."""
    try:
        parts = start_at.split(":")
        return int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
    except (ValueError, IndexError):
        return None


def _schedule_total_duration(schedule: ScheduleData) -> int:
    """Compute total duration in minutes for all zones in a schedule."""
    return sum(z.get("duration", 0) for z in schedule.get("zones", []))


def _events_for_schedule(
    schedule: ScheduleData,
    start_date: datetime,
    end_date: datetime,
) -> list[CalendarEvent]:
    """Generate CalendarEvent objects for a schedule within a date range."""
    if schedule.get("status") != "active":
        return []

    start_at = schedule.get("preferredTime", {}).get("startAt")
    if not start_at:
        return []

    parsed = _parse_start_time(start_at)
    if parsed is None:
        return []
    run_hour, run_minute = parsed

    total_minutes = _schedule_total_duration(schedule)
    if total_minutes <= 0:
        total_minutes = 30  # fallback

    events: list[CalendarEvent] = []
    current = start_date.replace(hour=0, minute=0, second=0, microsecond=0)

    while current <= end_date:
        if MoenDataUpdateCoordinator.matches_schedule_day(current, schedule):
            event_start = current.replace(hour=run_hour, minute=run_minute)
            if start_date <= event_start <= end_date:
                event_end = event_start + timedelta(minutes=total_minutes)
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
        """Return the next upcoming or active event."""
        now = dt_util.now()
        end = now + timedelta(days=14)

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
