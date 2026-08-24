"""Generate a memory from logical people spanning multiple Immich accounts."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from immich_memories.analysis.identity_source import (
    IdentitySelection,
    fetch_identity_live_photos,
    fetch_identity_photos,
    fetch_identity_videos,
    open_identity_clients,
)
from immich_memories.api.immich import SyncImmichClient
from immich_memories.cli._helpers import print_info, print_success
from immich_memories.cli._pipeline_runner import run_pipeline_and_generate

if TYPE_CHECKING:
    from immich_memories.cli._live_display import ProgressDisplay
    from immich_memories.config_loader import Config
    from immich_memories.timeperiod import DateRange


def handle_identity_generation(
    *,
    client: SyncImmichClient,
    config: Config,
    progress: ProgressDisplay,
    selection: IdentitySelection,
    annual_story: bool,
    date_ranges: list[DateRange],
    date_range: DateRange,
    use_live_photos: bool,
    use_photos: bool,
    analysis_depth: str,
    duration: float | None,
    transition: str,
    music: str | None,
    music_volume: float,
    no_music: bool,
    output_path: Path,
    resolution: str | None,
    orientation: str,
    scale_mode: str,
    output_format: str | None,
    add_date: bool,
    add_place: bool,
    keep_intermediates: bool,
    privacy_mode: bool,
    title_override: str | None,
    subtitle_override: str | None,
    llm_title: bool,
    memory_type: str | None,
    upload_to_immich: bool,
    album: str | None,
    source: str,
    memory_key: str | None,
    memory_category: str | None,
    automation_attempt_id: str | None,
    dry_run: bool,
    no_render: bool,
) -> tuple[Path, bool, str | None]:
    """Discover through each owner, then render through the primary client."""
    task = progress.add_task(f"Finding {selection.display_name} across accounts...", total=None)
    with open_identity_clients(config, selection) as clients:
        assets = fetch_identity_videos(selection, clients, date_ranges)
        photos = fetch_identity_photos(selection, clients, date_ranges) if use_photos else []
        if use_live_photos:
            live_clips, live_video_ids = fetch_identity_live_photos(
                selection, clients, date_ranges, config=config
            )
            assets = [asset for asset in assets if asset.id not in live_video_ids]
        else:
            live_clips = []
    progress.update(task, completed=True)

    print_success(
        f"Found {len(assets)} videos, {len(live_clips)} Live Photos, "
        f"and {len(photos)} photos for {selection.display_name}"
    )
    print_info(f"Boolean match: {selection.match.upper()} across {len(clients)} accounts")

    return run_pipeline_and_generate(
        assets=assets,
        live_photo_clips=live_clips,
        photo_assets=photos or None,
        include_photos=use_photos and bool(photos),
        analysis_depth=analysis_depth,
        client=client,
        config=config,
        progress=progress,
        duration=duration,
        transition=transition,
        music=music,
        music_volume=music_volume,
        no_music=no_music,
        output_path=output_path,
        output_resolution=resolution,
        output_orientation=orientation,
        scale_mode=scale_mode,
        output_format=output_format,
        add_date_overlay=add_date,
        add_place_overlay=add_place,
        debug_preserve_intermediates=keep_intermediates,
        privacy_mode=privacy_mode,
        title_override=title_override,
        subtitle_override=subtitle_override,
        llm_title=llm_title,
        memory_type=memory_type,
        person_names=[selection.display_name],
        date_range=date_range,
        upload_to_immich=upload_to_immich,
        album=album,
        memory_preset_params={
            "identity_kind": selection.kind,
            "identity_key": selection.key,
            "identity_match": selection.match,
            "subject_names": selection.subject_names,
            "annual_story": annual_story,
            "event_date": selection.event_date.isoformat() if selection.event_date else None,
        },
        source=source,
        memory_key=memory_key,
        memory_category=memory_category,
        automation_attempt_id=automation_attempt_id,
        dry_run=dry_run,
        no_render=no_render,
    )
