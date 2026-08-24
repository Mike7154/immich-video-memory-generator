"""Logical identity selection across separate Immich person databases."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

from immich_memories.analysis.identity_source import (
    fetch_identity_live_photos,
    fetch_identity_photos,
    fetch_identity_videos,
    resolve_identity_selection,
)
from immich_memories.api.models import Asset, AssetType, VideoClipInfo
from immich_memories.config_loader import Config
from immich_memories.config_models_identity import (
    IdentityAccountConfig,
    IdentityConfig,
    IdentityGroupConfig,
    LogicalSubjectConfig,
)
from immich_memories.timeperiod import DateRange


def _identity_config() -> IdentityConfig:
    return IdentityConfig(
        accounts={
            "michael": IdentityAccountConfig(api_key="michael-key"),
            "katie": IdentityAccountConfig(api_key="katie-key"),
        },
        subjects={
            "lucas": LogicalSubjectConfig(
                display_name="Lucas",
                people={"michael": "m-lucas", "katie": "k-lucas"},
            ),
            "asher": LogicalSubjectConfig(
                display_name="Asher",
                people={"michael": "m-asher", "katie": "k-asher"},
            ),
            "michael": LogicalSubjectConfig(
                display_name="Michael",
                people={"michael": "m-michael", "katie": "k-michael"},
            ),
            "katie": LogicalSubjectConfig(
                display_name="Katie",
                people={"michael": "m-katie", "katie": "k-katie"},
            ),
        },
        groups={
            "kids": IdentityGroupConfig(
                display_name="All Kids", subjects=["lucas", "asher"], match="any"
            ),
            "parents": IdentityGroupConfig(
                display_name="Michael & Katie",
                subjects=["michael", "katie"],
                match="all",
            ),
        },
    )


def test_any_group_builds_or_query_for_every_account() -> None:
    selection = resolve_identity_selection(_identity_config(), group="kids")

    assert selection.display_name == "All Kids"
    assert selection.match == "any"
    assert selection.account_people == {
        "michael": ["m-lucas", "m-asher"],
        "katie": ["k-lucas", "k-asher"],
    }


def test_all_group_builds_cooccurrence_query_for_every_account() -> None:
    selection = resolve_identity_selection(_identity_config(), group="parents")

    assert selection.match == "all"
    assert selection.subject_names == ["Michael", "Katie"]
    assert selection.account_people == {
        "michael": ["m-michael", "m-katie"],
        "katie": ["k-michael", "k-katie"],
    }


def test_required_plus_any_of_builds_union_of_cooccurrence_clauses() -> None:
    config = _identity_config()
    config.groups["mothers_day"] = IdentityGroupConfig(
        display_name="Mom & Kids",
        required=["katie"],
        any_of=["asher", "lucas"],
    )

    selection = resolve_identity_selection(config, group="mothers_day")

    assert selection.match == "composite"
    assert selection.account_clauses == {
        "michael": [
            ["m-katie", "m-asher"],
            ["m-katie", "m-lucas"],
        ],
        "katie": [
            ["k-katie", "k-asher"],
            ["k-katie", "k-lucas"],
        ],
    }


def _asset(asset_id: str, checksum: str) -> Asset:
    now = datetime(2026, 1, 1)
    return Asset(
        id=asset_id,
        type=AssetType.VIDEO,
        fileCreatedAt=now,
        fileModifiedAt=now,
        updatedAt=now,
        checksum=checksum,
    )


class _DiscoveryClient:
    def __init__(self, assets_by_person: dict[str, list[Asset]]) -> None:
        self.assets_by_person = assets_by_person
        self.single_calls: list[str] = []
        self.all_calls: list[list[str]] = []
        self.photo_calls: list[tuple[str | None, list[str] | None]] = []

    def get_videos_for_person_and_date_range(self, person_id, _date_range):
        self.single_calls.append(person_id)
        return self.assets_by_person[person_id]

    def get_videos_for_all_persons(self, person_ids, _date_range):
        self.all_calls.append(person_ids)
        common_ids = set.intersection(
            *({asset.id for asset in self.assets_by_person[person]} for person in person_ids)
        )
        return [asset for asset in self.assets_by_person[person_ids[0]] if asset.id in common_ids]

    def get_photos_for_date_range(self, _date_range, *, person_id=None, person_ids=None):
        self.photo_calls.append((person_id, person_ids))
        if person_id:
            return self.assets_by_person[person_id]
        common_ids = set.intersection(
            *({asset.id for asset in self.assets_by_person[person]} for person in person_ids)
        )
        return [asset for asset in self.assets_by_person[person_ids[0]] if asset.id in common_ids]


def test_any_group_unions_accounts_and_deduplicates_same_original() -> None:
    shared_a = _asset("m-shared", "same-checksum")
    shared_b = _asset("k-shared", "same-checksum")
    clients = {
        "michael": _DiscoveryClient(
            {"m-lucas": [shared_a], "m-asher": [_asset("m-asher-only", "asher")]}
        ),
        "katie": _DiscoveryClient(
            {"k-lucas": [shared_b], "k-asher": [_asset("k-asher-only", "k-asher")]}
        ),
    }

    videos = fetch_identity_videos(
        resolve_identity_selection(_identity_config(), group="kids"),
        clients,
        [DateRange(start=datetime(2026, 1, 1), end=datetime(2026, 12, 31))],
    )

    assert [asset.id for asset in videos] == ["m-shared", "m-asher-only", "k-asher-only"]
    assert clients["michael"].single_calls == ["m-lucas", "m-asher"]
    assert clients["katie"].single_calls == ["k-lucas", "k-asher"]


def test_all_group_intersects_people_inside_each_account() -> None:
    together = _asset("together", "together")
    clients = {
        "michael": _DiscoveryClient(
            {
                "m-michael": [together, _asset("michael-only", "michael-only")],
                "m-katie": [together],
            }
        ),
        "katie": _DiscoveryClient(
            {
                "k-michael": [],
                "k-katie": [_asset("katie-only", "katie-only")],
            }
        ),
    }

    videos = fetch_identity_videos(
        resolve_identity_selection(_identity_config(), group="parents"),
        clients,
        [DateRange(start=datetime(2026, 1, 1), end=datetime(2026, 12, 31))],
    )

    assert [asset.id for asset in videos] == ["together"]
    assert clients["michael"].all_calls == [["m-michael", "m-katie"]]
    assert clients["katie"].all_calls == [["k-michael", "k-katie"]]


def test_required_plus_any_of_keeps_mom_with_at_least_one_kid() -> None:
    config = _identity_config()
    config.groups["mothers_day"] = IdentityGroupConfig(
        display_name="Mom & Kids",
        required=["katie"],
        any_of=["asher", "lucas"],
    )
    mom_asher = _asset("mom-asher", "mom-asher")
    mom_lucas = _asset("mom-lucas", "mom-lucas")
    mom_only = _asset("mom-only", "mom-only")
    clients = {
        "michael": _DiscoveryClient(
            {
                "m-katie": [mom_asher, mom_lucas, mom_only],
                "m-asher": [mom_asher],
                "m-lucas": [mom_lucas],
            }
        ),
        "katie": _DiscoveryClient(
            {
                "k-katie": [],
                "k-asher": [],
                "k-lucas": [],
            }
        ),
    }
    date_ranges = [DateRange(start=datetime(2026, 1, 1), end=datetime(2026, 12, 31))]
    selection = resolve_identity_selection(config, group="mothers_day")

    videos = fetch_identity_videos(selection, clients, date_ranges)
    photos = fetch_identity_photos(selection, clients, date_ranges)

    assert [asset.id for asset in videos] == ["mom-asher", "mom-lucas"]
    assert [asset.id for asset in photos] == ["mom-asher", "mom-lucas"]
    assert ["m-katie", "m-asher"] in clients["michael"].all_calls
    assert ["m-katie", "m-lucas"] in clients["michael"].all_calls


def test_photo_queries_follow_the_same_any_and_all_rules() -> None:
    together = _asset("together", "together")
    clients = {
        "michael": _DiscoveryClient(
            {
                "m-lucas": [_asset("lucas", "lucas")],
                "m-asher": [_asset("asher", "asher")],
                "m-michael": [together],
                "m-katie": [together],
            }
        ),
        "katie": _DiscoveryClient(
            {
                "k-lucas": [],
                "k-asher": [],
                "k-michael": [],
                "k-katie": [],
            }
        ),
    }
    date_ranges = [DateRange(start=datetime(2026, 1, 1), end=datetime(2026, 12, 31))]

    any_photos = fetch_identity_photos(
        resolve_identity_selection(_identity_config(), group="kids"), clients, date_ranges
    )
    all_photos = fetch_identity_photos(
        resolve_identity_selection(_identity_config(), group="parents"), clients, date_ranges
    )

    assert [asset.id for asset in any_photos] == ["lucas", "asher"]
    assert [asset.id for asset in all_photos] == ["together"]
    assert (None, ["m-michael", "m-katie"]) in clients["michael"].photo_calls


def test_live_photo_queries_use_boolean_mode_per_account() -> None:
    calls: list[tuple[str | None, list[str] | None]] = []

    def fake_fetcher(_client, _range, person_id=None, person_ids=None, *, config):
        calls.append((person_id, person_ids))
        person_key = person_id or "-".join(person_ids)
        asset = _asset(f"live-{person_key}", f"checksum-{person_key}")
        asset.type = AssetType.IMAGE
        asset.live_photo_video_id = f"video-{person_key}"
        return [VideoClipInfo(asset=asset, duration_seconds=3)], {asset.live_photo_video_id}

    clients = {
        "michael": _DiscoveryClient({}),
        "katie": _DiscoveryClient({}),
    }
    date_ranges = [DateRange(start=datetime(2026, 1, 1), end=datetime(2026, 12, 31))]

    # WHY: real Live Photo discovery crosses the Immich API boundary; this test
    # exercises only the identity-source Boolean routing around that boundary.
    with patch(
        "immich_memories.analysis.identity_source.fetch_live_photo_clips",
        side_effect=fake_fetcher,
    ):
        any_clips, _ = fetch_identity_live_photos(
            resolve_identity_selection(_identity_config(), group="kids"),
            clients,
            date_ranges,
            config=Config(),
        )
        all_clips, _ = fetch_identity_live_photos(
            resolve_identity_selection(_identity_config(), group="parents"),
            clients,
            date_ranges,
            config=Config(),
        )

    assert len(any_clips) == 4
    assert len(all_clips) == 2
    assert (None, ["m-michael", "m-katie"]) in calls
