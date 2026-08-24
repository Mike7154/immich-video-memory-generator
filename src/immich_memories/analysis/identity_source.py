"""Resolve logical people into per-account Immich person queries."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Literal, Protocol, cast

from immich_memories.analysis.live_photo_pipeline import fetch_live_photo_clips
from immich_memories.api.models import Asset, VideoClipInfo
from immich_memories.config_models_identity import IdentityConfig
from immich_memories.timeperiod import DateRange

if TYPE_CHECKING:
    from immich_memories.api.immich import SyncImmichClient
    from immich_memories.config_loader import Config


class IdentityDiscoveryClient(Protocol):
    """The read-only calls needed for logical media selection."""

    def get_videos_for_person_and_date_range(
        self, person_id: str, date_range: DateRange
    ) -> list[Asset]: ...

    def get_videos_for_all_persons(
        self, person_ids: list[str], date_range: DateRange
    ) -> list[Asset]: ...

    def get_photos_for_date_range(
        self,
        date_range: DateRange,
        *,
        person_id: str | None = None,
        person_ids: list[str] | None = None,
    ) -> list[Asset]: ...


@dataclass(frozen=True, slots=True)
class IdentitySelection:
    """A Boolean identity selection expressed in each account's person IDs."""

    key: str
    kind: Literal["subject", "group"]
    display_name: str
    subject_names: list[str]
    match: Literal["any", "all"]
    account_people: dict[str, list[str]]
    birth_date: date | None = None
    event_date: date | None = None


@contextmanager
def open_identity_clients(
    config: Config, selection: IdentitySelection
) -> Iterator[dict[str, IdentityDiscoveryClient]]:
    """Open one discovery client for every account participating in a selection."""
    from immich_memories.api.immich import SyncImmichClient

    with ExitStack() as stack:
        clients: dict[str, IdentityDiscoveryClient] = {}
        for account in selection.account_people:
            account_config = config.identities.accounts[account]
            clients[account] = stack.enter_context(
                SyncImmichClient(
                    base_url=account_config.url or config.immich.url,
                    api_key=account_config.api_key,
                    api_version=account_config.api_version or config.immich.api_version,
                )
            )
        yield clients


def resolve_identity_selection(
    config: IdentityConfig,
    *,
    subject: str | None = None,
    group: str | None = None,
) -> IdentitySelection:
    """Resolve exactly one configured subject or group into account-local IDs."""
    if bool(subject) == bool(group):
        raise ValueError("Choose exactly one logical subject or identity group")
    if subject:
        return _resolve_subject(config, subject)
    return _resolve_group(config, group or "")


def _resolve_subject(config: IdentityConfig, key: str) -> IdentitySelection:
    try:
        logical = config.subjects[key]
    except KeyError as exc:
        raise ValueError(f"Unknown logical subject: {key}") from exc
    return IdentitySelection(
        key=key,
        kind="subject",
        display_name=logical.display_name,
        subject_names=[logical.display_name],
        match="any",
        account_people={account: [person_id] for account, person_id in logical.people.items()},
        birth_date=logical.birth_date,
        event_date=logical.birth_date,
    )


def _resolve_group(config: IdentityConfig, key: str) -> IdentitySelection:
    try:
        group = config.groups[key]
    except KeyError as exc:
        raise ValueError(f"Unknown identity group: {key}") from exc

    subjects = [config.subjects[subject] for subject in group.subjects]
    account_people: dict[str, list[str]] = {}
    for account in config.accounts:
        person_ids = [subject.people[account] for subject in subjects if account in subject.people]
        if group.match == "all" and len(person_ids) != len(subjects):
            continue
        if person_ids:
            account_people[account] = person_ids

    if not account_people:
        raise ValueError(f"Identity group {key!r} has no complete account mapping")

    return IdentitySelection(
        key=key,
        kind="group",
        display_name=group.display_name,
        subject_names=[subject.display_name for subject in subjects],
        match=group.match,
        account_people=account_people,
        event_date=group.event_date,
    )


def fetch_identity_videos(
    selection: IdentitySelection,
    clients: dict[str, IdentityDiscoveryClient],
    date_ranges: list[DateRange],
) -> list[Asset]:
    """Fetch and combine videos matching a logical selection across accounts."""
    discovered: list[Asset] = []
    for account, person_ids in selection.account_people.items():
        client = clients[account]
        for date_range in date_ranges:
            if selection.match == "all" and len(person_ids) > 1:
                discovered.extend(client.get_videos_for_all_persons(person_ids, date_range))
                continue
            for person_id in person_ids:
                discovered.extend(
                    client.get_videos_for_person_and_date_range(person_id, date_range)
                )
    return _deduplicate_assets(discovered)


def fetch_identity_photos(
    selection: IdentitySelection,
    clients: dict[str, IdentityDiscoveryClient],
    date_ranges: list[DateRange],
) -> list[Asset]:
    """Fetch and combine still photos matching a logical selection."""
    discovered: list[Asset] = []
    for account, person_ids in selection.account_people.items():
        client = clients[account]
        for date_range in date_ranges:
            if selection.match == "all" and len(person_ids) > 1:
                discovered.extend(
                    client.get_photos_for_date_range(date_range, person_ids=person_ids)
                )
                continue
            for person_id in person_ids:
                discovered.extend(client.get_photos_for_date_range(date_range, person_id=person_id))
    return _deduplicate_assets(discovered)


def fetch_identity_live_photos(
    selection: IdentitySelection,
    clients: dict[str, IdentityDiscoveryClient],
    date_ranges: list[DateRange],
    *,
    config: Config,
) -> tuple[list[VideoClipInfo], set[str]]:
    """Fetch Live Photo clips using the same account-local Boolean semantics."""
    discovered: list[VideoClipInfo] = []
    video_ids: set[str] = set()
    for account, person_ids in selection.account_people.items():
        client = clients[account]
        live_client = cast("SyncImmichClient", client)
        for date_range in date_ranges:
            if selection.match == "all" and len(person_ids) > 1:
                clips, ids = fetch_live_photo_clips(
                    live_client, date_range, person_ids=person_ids, config=config
                )
                discovered.extend(clips)
                video_ids.update(ids)
                continue
            for person_id in person_ids:
                clips, ids = fetch_live_photo_clips(
                    live_client, date_range, person_id=person_id, config=config
                )
                discovered.extend(clips)
                video_ids.update(ids)
    return _deduplicate_clips(discovered), video_ids


def _deduplicate_assets(assets: list[Asset]) -> list[Asset]:
    seen: set[str] = set()
    unique: list[Asset] = []
    for asset in assets:
        identity = asset.checksum or asset.id
        if identity not in seen:
            seen.add(identity)
            unique.append(asset)
    unique.sort(key=lambda asset: asset.file_created_at)
    return unique


def _deduplicate_clips(clips: list[VideoClipInfo]) -> list[VideoClipInfo]:
    seen: set[str] = set()
    unique: list[VideoClipInfo] = []
    for clip in clips:
        identity = clip.asset.checksum or clip.asset.id
        if identity not in seen:
            seen.add(identity)
            unique.append(clip)
    unique.sort(key=lambda clip: clip.asset.file_created_at)
    return unique
