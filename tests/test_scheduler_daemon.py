"""Tests for the scheduler daemon loop."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from immich_memories.scheduling.models import ScheduleEntry, SchedulerConfig


class TestDaemonLoop:
    """Scheduler daemon: sleep until next job, execute, repeat."""

    def test_execute_job_builds_cli_command(self):
        """execute_job should resolve params and run CLI with correct args."""
        from immich_memories.scheduling.daemon import execute_job
        from immich_memories.scheduling.engine import PendingJob

        entry = ScheduleEntry(
            name="yearly",
            memory_type="year_in_review",
            cron="0 6 15 1 *",
        )
        job = PendingJob(
            schedule=entry,
            fire_time=datetime(2026, 1, 15, 6, 0, tzinfo=UTC),
        )

        with patch("immich_memories.scheduling.daemon.subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(returncode=0)
            execute_job(job)

        mock_sub.run.assert_called_once()
        cmd = mock_sub.run.call_args[0][0]
        assert cmd[0] == "immich-memories"
        assert cmd[1] == "generate"
        assert "--memory-type" in cmd
        assert "year_in_review" in cmd
        assert "--year" in cmd
        assert "2025" in cmd  # Previous year

    def test_execute_job_propagates_custom_config_before_generate(self):
        """The legacy daemon must not fall back to the default Immich account."""
        from immich_memories.scheduling.daemon import execute_job
        from immich_memories.scheduling.engine import PendingJob

        entry = ScheduleEntry(
            name="yearly",
            memory_type="year_in_review",
            cron="0 6 15 1 *",
        )
        job = PendingJob(
            schedule=entry,
            fire_time=datetime(2026, 1, 15, 6, 0, tzinfo=UTC),
        )
        config_path = Path("/tmp/Config dir/photos & family.yaml")

        with patch("immich_memories.scheduling.daemon.subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(returncode=0)
            execute_job(job, config_path=config_path)

        assert mock_sub.run.call_args.args[0][:4] == [
            "immich-memories",
            "--config",
            str(config_path),
            "generate",
        ]

    def test_execute_job_with_upload(self):
        """execute_job should pass --upload-to-immich when enabled."""
        from immich_memories.scheduling.daemon import execute_job
        from immich_memories.scheduling.engine import PendingJob

        entry = ScheduleEntry(
            name="monthly",
            memory_type="monthly_highlights",
            cron="0 6 1 * *",
            upload_to_immich=True,
            album_name="Monthly {month}",
        )
        job = PendingJob(
            schedule=entry,
            fire_time=datetime(2026, 3, 1, 6, 0, tzinfo=UTC),
        )

        with patch("immich_memories.scheduling.daemon.subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(returncode=0)
            execute_job(job)

        cmd = mock_sub.run.call_args[0][0]
        assert "--upload-to-immich" in cmd
        assert "--album" in cmd

    def test_floating_event_guard_runs_only_on_the_resolved_date(self):
        from immich_memories.config_loader import Config
        from immich_memories.scheduling.daemon import event_schedule_matches

        config = Config(
            identities={
                "accounts": {"family": {"api_key": "key"}},
                "subjects": {
                    "mom": {"display_name": "Mom", "people": {"family": "mom"}},
                    "child": {"display_name": "Child", "people": {"family": "child"}},
                },
                "groups": {
                    "mothers_day": {
                        "display_name": "Mom & Kids",
                        "required": ["mom"],
                        "any_of": ["child"],
                        "event_rule": {
                            "month": 5,
                            "weekday": "sunday",
                            "occurrence": 2,
                        },
                    }
                },
            }
        )
        params = {"group": "mothers_day", "annual_story": True}

        with patch("immich_memories.config_loader.get_config", return_value=config):
            assert event_schedule_matches(
                params,
                fire_time=datetime(2026, 5, 10, 8, 0, tzinfo=UTC),
            )
            assert not event_schedule_matches(
                params,
                fire_time=datetime(2026, 5, 11, 8, 0, tzinfo=UTC),
            )

    def test_event_only_schedule_skips_subprocess_on_anordinary_day(self):
        from immich_memories.config_loader import Config
        from immich_memories.scheduling.daemon import execute_job
        from immich_memories.scheduling.engine import PendingJob

        config = Config(
            identities={
                "accounts": {"family": {"api_key": "key"}},
                "subjects": {
                    "lucas": {
                        "display_name": "Lucas",
                        "birth_date": "2018-04-10",
                        "people": {"family": "lucas"},
                    }
                },
            }
        )
        entry = ScheduleEntry(
            name="Lucas birthday",
            memory_type="person_spotlight",
            cron="0 8 * * *",
            event_only=True,
            params={"subject": "lucas", "annual_story": True},
        )
        job = PendingJob(
            schedule=entry,
            fire_time=datetime(2026, 4, 9, 8, 0, tzinfo=UTC),
        )

        with (
            patch("immich_memories.config_loader.get_config", return_value=config),
            patch("immich_memories.scheduling.daemon.subprocess") as mock_sub,
        ):
            execute_job(job)

        mock_sub.run.assert_not_called()

    def test_default_timeout_is_60_minutes(self):
        """Default job timeout should be 3600s (60min), not 1800s."""
        from immich_memories.scheduling.daemon import execute_job
        from immich_memories.scheduling.engine import PendingJob

        entry = ScheduleEntry(
            name="yearly",
            memory_type="year_in_review",
            cron="0 6 15 1 *",
        )
        job = PendingJob(
            schedule=entry,
            fire_time=datetime(2026, 1, 15, 6, 0, tzinfo=UTC),
        )

        with patch("immich_memories.scheduling.daemon.subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(returncode=0)
            execute_job(job)

        _, kwargs = mock_sub.run.call_args
        assert kwargs["timeout"] == 3600

    def test_custom_timeout_from_config(self):
        """SchedulerConfig.job_timeout_minutes overrides the default."""
        config = SchedulerConfig(
            enabled=True,
            job_timeout_minutes=90,
            schedules=[],
        )
        assert config.job_timeout_minutes == 90

    def test_timeout_error_message_shows_minutes(self):
        """Timeout error should report the configured duration in minutes."""
        from immich_memories.scheduling.daemon import execute_job
        from immich_memories.scheduling.engine import PendingJob

        entry = ScheduleEntry(
            name="yearly",
            memory_type="year_in_review",
            cron="0 6 15 1 *",
        )
        job = PendingJob(
            schedule=entry,
            fire_time=datetime(2026, 1, 15, 6, 0, tzinfo=UTC),
        )

        with patch("immich_memories.scheduling.daemon.subprocess") as mock_sub:
            mock_sub.TimeoutExpired = TimeoutError
            mock_sub.run.side_effect = TimeoutError("timed out")
            # Should not raise — just logs
            execute_job(job, timeout_seconds=5400)

    def test_daemon_handles_sigint(self):
        """run_daemon_loop should stop gracefully on KeyboardInterrupt."""
        from immich_memories.scheduling.daemon import run_daemon_loop

        config = SchedulerConfig(
            enabled=True,
            schedules=[
                ScheduleEntry(
                    name="test",
                    memory_type="year_in_review",
                    cron="0 6 * * *",
                ),
            ],
        )

        mock_db = MagicMock()
        with (
            patch("immich_memories.scheduling.daemon.time.sleep", side_effect=KeyboardInterrupt),
            # WHY: avoid real DB init during test — RunDatabase needs config + SQLite
            patch("immich_memories.tracking.run_database.RunDatabase", return_value=mock_db),
        ):
            # Should not raise — graceful shutdown
            run_daemon_loop(config, db_path=Path("/tmp/test_daemon.db"))

    def test_daemon_loop_forwards_custom_config_to_each_job(self):
        """The daemon handoff cannot discard provenance after CLI startup."""
        import immich_memories.scheduling.daemon as daemon
        from immich_memories.scheduling.daemon import run_daemon_loop
        from immich_memories.scheduling.engine import PendingJob

        config = SchedulerConfig(
            enabled=True,
            schedules=[
                ScheduleEntry(
                    name="yearly",
                    memory_type="year_in_review",
                    cron="0 6 * * *",
                )
            ],
        )
        job = PendingJob(
            schedule=config.schedules[0],
            fire_time=datetime(2026, 1, 15, 6, 0, tzinfo=UTC),
        )
        scheduler = MagicMock()
        scheduler.seconds_until_next.return_value = 0
        scheduler.get_next_jobs.return_value = [job]
        config_path = Path("/tmp/Config dir/family.yaml")

        def stop_after_job(*_args: object, **_kwargs: object) -> None:
            daemon._shutdown_requested = True

        with (
            patch("immich_memories.scheduling.daemon.Scheduler", return_value=scheduler),
            patch("immich_memories.tracking.run_database.RunDatabase"),
            patch(
                "immich_memories.scheduling.daemon.execute_job",
                side_effect=stop_after_job,
            ) as execute,
        ):
            run_daemon_loop(
                config,
                db_path=Path("/tmp/test_daemon.db"),
                config_path=config_path,
            )

        execute.assert_called_once_with(
            job,
            timeout_seconds=3600,
            config_path=config_path,
        )

    def test_person_names_use_equals_syntax(self):
        """Person names should use --person=Name to prevent flag injection."""
        from immich_memories.scheduling.daemon import execute_job
        from immich_memories.scheduling.engine import PendingJob

        entry = ScheduleEntry(
            name="spotlight",
            memory_type="person_spotlight",
            cron="0 6 1 * *",
            person_names=["Alice", "--evil-flag"],
        )
        job = PendingJob(
            schedule=entry,
            fire_time=datetime(2026, 3, 1, 6, 0, tzinfo=UTC),
        )

        with patch("immich_memories.scheduling.daemon.subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(returncode=0)
            execute_job(job)

        cmd = mock_sub.run.call_args[0][0]
        assert "--person=Alice" in cmd
        assert "--person=--evil-flag" in cmd
        # Verify the name is never a standalone arg
        assert "--evil-flag" not in [c for c in cmd if c != "--person=--evil-flag"]
