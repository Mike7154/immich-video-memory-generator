"""Date windows for annual-event history plus the most recent event year."""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta

from immich_memories.memory_types.date_builders import build_on_this_day
from immich_memories.timeperiod import DateRange


def annual_story_scope(
    event_date: date,
    *,
    event_year: int,
    years_back: int | None = None,
) -> tuple[DateRange, list[DateRange]]:
    """Combine past event-day windows with the year ending on this occurrence.

    The rolling range begins the day after the previous occurrence, so that
    occurrence remains represented by its dedicated +/-1-day history window.
    Discovery later deduplicates the intentional one-day overlap.
    """
    occurrence = _occurrence_in_year(event_date, event_year)
    history = build_on_this_day(occurrence, years_back=years_back)
    previous = _occurrence_in_year(event_date, event_year - 1)
    recent = DateRange(
        start=datetime.combine(previous + timedelta(days=1), datetime.min.time()),
        end=datetime.combine(occurrence, datetime.max.time().replace(microsecond=0)),
    )
    ranges = [recent, *history]
    display = DateRange(
        start=min(window.start for window in ranges),
        end=max(window.end for window in ranges),
    )
    return display, ranges


def _occurrence_in_year(event_date: date, year: int) -> date:
    day = event_date.day
    if event_date.month == 2 and day == 29 and not calendar.isleap(year):
        day = 28
    return date(year, event_date.month, day)
