"""Date windows for annual-event history plus the most recent event year."""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta

from immich_memories.config_models_identity import FloatingAnnualEventConfig
from immich_memories.memory_types.date_builders import build_on_this_day
from immich_memories.timeperiod import DateRange


def annual_story_scope(
    event_date: date | None,
    *,
    event_rule: FloatingAnnualEventConfig | None = None,
    event_year: int,
    years_back: int | None = None,
) -> tuple[DateRange, list[DateRange]]:
    """Combine past event-day windows with the year ending on this occurrence.

    The rolling range begins the day after the previous occurrence, so that
    occurrence remains represented by its dedicated +/-1-day history window.
    Discovery later deduplicates the intentional one-day overlap.
    """
    occurrence = event_occurrence(event_date, event_rule=event_rule, year=event_year)
    previous = event_occurrence(event_date, event_rule=event_rule, year=event_year - 1)
    history = (
        _floating_event_history(event_rule, event_year=event_year, years_back=years_back)
        if event_rule is not None
        else build_on_this_day(occurrence, years_back=years_back)
    )
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


def event_occurrence(
    event_date: date | None,
    *,
    event_rule: FloatingAnnualEventConfig | None,
    year: int,
) -> date:
    """Resolve either a fixed month/day or a floating weekday rule in one year."""
    if (event_date is None) == (event_rule is None):
        raise ValueError("Choose exactly one of event_date or event_rule")
    if event_rule is not None:
        return event_rule.date_for_year(year)
    assert event_date is not None
    return _occurrence_in_year(event_date, year)


def _floating_event_history(
    event_rule: FloatingAnnualEventConfig,
    *,
    event_year: int,
    years_back: int | None,
) -> list[DateRange]:
    """Build +/-1-day windows around the rule's true occurrence in prior years."""
    effective_years_back = years_back if years_back is not None else 30
    if effective_years_back <= 0:
        return []
    windows: list[DateRange] = []
    for offset in range(1, effective_years_back + 1):
        center = event_rule.date_for_year(event_year - offset)
        windows.append(
            DateRange(
                start=datetime.combine(center - timedelta(days=1), datetime.min.time()),
                end=datetime.combine(
                    center + timedelta(days=1),
                    datetime.max.time().replace(microsecond=0),
                ),
            )
        )
    return windows


def _occurrence_in_year(event_date: date, year: int) -> date:
    day = event_date.day
    if event_date.month == 2 and day == 29 and not calendar.isleap(year):
        day = 28
    return date(year, event_date.month, day)
