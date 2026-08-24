"""Annual stories combine event-day history with the latest event year."""

from datetime import date

from immich_memories.analysis.annual_story import annual_story_scope
from immich_memories.analysis.identity_source import resolve_identity_selection
from immich_memories.config_models_identity import (
    IdentityAccountConfig,
    IdentityConfig,
    IdentityGroupConfig,
    LogicalSubjectConfig,
)


def test_annual_story_has_historical_event_windows_and_latest_year() -> None:
    display, windows = annual_story_scope(date(2018, 4, 10), event_year=2026, years_back=3)

    assert len(windows) == 4
    assert windows[0].start.date() == date(2025, 4, 11)
    assert windows[0].end.date() == date(2026, 4, 10)
    assert [window.start.date() for window in windows[1:]] == [
        date(2025, 4, 9),
        date(2024, 4, 9),
        date(2023, 4, 9),
    ]
    assert display.start.date() == date(2023, 4, 9)
    assert display.end.date() == date(2026, 4, 10)


def test_annual_story_handles_leap_day() -> None:
    _display, windows = annual_story_scope(date(2020, 2, 29), event_year=2025, years_back=1)

    assert windows[0].start.date() == date(2024, 3, 1)
    assert windows[0].end.date() == date(2025, 2, 28)


def test_subject_birth_date_and_group_event_date_resolve_generically() -> None:
    config = IdentityConfig(
        accounts={"family": IdentityAccountConfig(api_key="key")},
        subjects={
            "lucas": LogicalSubjectConfig(
                display_name="Lucas",
                birth_date=date(2018, 4, 10),
                people={"family": "lucas-id"},
            ),
            "michael": LogicalSubjectConfig(
                display_name="Michael", people={"family": "michael-id"}
            ),
            "katie": LogicalSubjectConfig(display_name="Katie", people={"family": "katie-id"}),
        },
        groups={
            "anniversary": IdentityGroupConfig(
                display_name="Michael & Katie",
                subjects=["michael", "katie"],
                match="all",
                event_date=date(2012, 9, 22),
            )
        },
    )

    assert resolve_identity_selection(config, subject="lucas").event_date == date(2018, 4, 10)
    anniversary = resolve_identity_selection(config, group="anniversary")
    assert anniversary.match == "all"
    assert anniversary.event_date == date(2012, 9, 22)
