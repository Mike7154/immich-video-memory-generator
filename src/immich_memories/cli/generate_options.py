"""Scope and option resolution shared by the generate command and its tests."""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import click

from immich_memories.cli._date_resolution import resolve_date_range
from immich_memories.cli._helpers import print_error
from immich_memories.timeperiod import DateRange

if TYPE_CHECKING:
    from immich_memories.analysis.identity_source import IdentitySelection
    from immich_memories.config_loader import Config


def resolve_generation_scope(
    *,
    from_album: str | None,
    year: int | None,
    start: str | None,
    end: str | None,
    period: str | None,
    birthday: str | None,
    memory_type: str | None,
    season: str | None,
    month: int | None,
    hemisphere: str,
    years_back: int | None,
    on_this_day_target: date | None,
    holiday: str | None = None,
) -> tuple[DateRange, list[DateRange]]:
    """Resolve the display range and one or more discovery ranges."""
    if from_album:
        now = datetime.now()
        return DateRange(start=now, end=now), []

    # WHY: birthday="auto" means detect from Immich later — don't pass to parser.
    initial_birthday = None if birthday == "auto" else birthday
    date_result = resolve_date_range(
        year,
        start,
        end,
        period,
        initial_birthday,
        memory_type=memory_type,
        season=season,
        month=month,
        hemisphere=hemisphere,
        years_back=years_back,
        on_this_day_target=on_this_day_target,
        holiday=holiday,
    )

    if not isinstance(date_result, list):
        return date_result, [date_result]
    if not date_result:
        print_error("No date ranges generated for On This Day")
        sys.exit(1)
    return DateRange(start=date_result[-1].start, end=date_result[0].end), date_result


def reject_album_scope_conflicts(
    *,
    year: int | None,
    start: str | None,
    end: str | None,
    period: str | None,
    birthday: str | None,
    season: str | None,
    month: int | None,
    memory_type: str | None,
    person_names: list[str] | tuple[str, ...],
    subject: str | None = None,
    identity_group: str | None = None,
    annual_story: bool = False,
) -> None:
    """Reject date/person filters when an album already defines the assets."""
    conflicts = {
        "--year": year,
        "--start": start,
        "--end": end,
        "--period": period,
        "--birthday": birthday,
        "--season": season,
        "--month": month,
        "--memory-type": memory_type,
        "--person": person_names,
        "--subject": subject,
        "--group": identity_group,
        "--annual-story": annual_story,
    }
    used = sorted(flag for flag, value in conflicts.items() if value)
    if used:
        raise click.UsageError(f"--from-album selects its own assets; drop {', '.join(used)}")


SHORT_FORM_SECONDS = ("15", "30", "60", "90")


@dataclass(frozen=True, slots=True)
class ShortForm:
    """What a short-form preset resolves to."""

    duration: float | None
    orientation: str


def resolve_short_form(
    short_form: str | None,
    *,
    duration: float | None,
    orientation: str,
    orientation_was_given: bool = False,
) -> ShortForm:
    """Apply the preset only where an explicit CLI value did not win."""
    if short_form is None:
        return ShortForm(duration=duration, orientation=orientation)
    return ShortForm(
        duration=duration if duration is not None else int(short_form),
        orientation=orientation if orientation_was_given else "portrait",
    )


def apply_scalar_overrides(
    config: Config,
    *,
    photo_duration: float | None,
    refinement_passes: int | None,
) -> None:
    """Let a flag outrank the config file for dials that have both."""
    if photo_duration is not None:
        config.photos.duration = photo_duration
    if refinement_passes is not None:
        config.analysis.max_refinement_passes = refinement_passes


def resolve_inclusion(flag: bool | None, *, config_enabled: bool) -> bool:
    """Resolve an optional inclusion flag, falling back to config."""
    if flag is None:
        return config_enabled
    return flag


def arm_selection_trace(path: Path | None) -> None:
    """Tell run_selection where to write its stage-by-stage report."""
    if path:
        os.environ["IMMICH_MEMORIES_SELECTION_TRACE"] = str(path)


def validate_annual_story_options(
    enabled: bool,
    *,
    selection: IdentitySelection | None,
    year: int | None,
    scope_values: Mapping[str, object],
) -> int | None:
    """Validate annual-story identity/date ownership and resolve its event year."""
    if not enabled:
        return year
    if selection is None:
        raise click.UsageError("--annual-story requires --subject or --group")
    if selection.event_date is None:
        section = "subjects" if selection.kind == "subject" else "groups"
        field = "birth_date" if selection.kind == "subject" else "event_date"
        raise click.UsageError(f"Set identities.{section}.{selection.key}.{field} in config.yaml")
    if used := [flag for flag, value in scope_values.items() if value]:
        raise click.UsageError(f"--annual-story defines its own dates; drop {', '.join(used)}")
    return year or date.today().year


def build_annual_story_scope(
    enabled: bool,
    selection: IdentitySelection | None,
    memory_type: str | None,
    year: int | None,
    years_back: int | None,
) -> tuple[DateRange, list[DateRange]] | None:
    """Build validated annual-story windows, or return None for a normal run."""
    if not enabled:
        return None
    assert selection is not None
    expected_type = "person_spotlight" if selection.kind == "subject" else "multi_person"
    if memory_type != expected_type:
        raise click.UsageError(
            f"--annual-story with this selection requires --memory-type {expected_type}"
        )
    assert selection.event_date is not None
    assert year is not None
    from immich_memories.analysis.annual_story import annual_story_scope

    return annual_story_scope(selection.event_date, event_year=year, years_back=years_back)
