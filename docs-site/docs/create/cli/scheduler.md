---
sidebar_position: 4
title: scheduler
---

# scheduler

:::tip The `auto` system is the easier option
Most users should schedule one daily [`auto run`](./auto.md#auto-run) instead: it detects trips,
birthdays, and highlights automatically. No cron expressions or explicit schedules needed. The
scheduler below is the advanced/legacy cron daemon for Docker/K8s deployments or exact control
over what generates when.
:::

:::caution Background mode not yet implemented
The scheduler daemon currently requires `--foreground` to run. Background (daemonized) mode is planned but not yet implemented. Always pass `--foreground` when starting the scheduler.
:::

## scheduler list

```bash
immich-memories scheduler list
```

Shows all configured schedules: name, memory type, cron expression, enabled/disabled, upload setting, and next run time.

If nothing's configured, you get a hint pointing you to the config file.

## scheduler status

```bash
immich-memories scheduler status
```

Quick overview: is the scheduler enabled, how many schedules are active, when the next job fires.

## scheduler start

```bash
immich-memories scheduler start --foreground
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--foreground` | flag | `false` | Run in foreground (required: background mode is not yet implemented) |

Starts the advanced/legacy scheduler daemon. Needs `scheduler.enabled: true` and at least one
schedule in the config. It is separate from `auto run`; do not run both daily unless you deliberately
want independent automation paths.

## Auto-resolved parameters

When a schedule fires, date parameters get resolved automatically from the fire time:

| Memory type | What gets filled in |
|-------------|---------------------|
| `year_in_review` | `year` = previous year |
| `monthly_highlights` | `year` + `month` = previous month |
| `on_this_day` | `target_date` = fire date |
| `trip` | `year` = previous year (scans GPS data, generates all trips) |

So a `year_in_review` firing on Jan 15 2025 generates for 2024. A `monthly_highlights` firing on Aug 1 generates for July. You get the idea.

Explicit `params` in the schedule config override these auto-resolved values. Setting `params: { year: 2020 }` on a `year_in_review` schedule always generates for 2020 no matter when it fires.

## Example config

```yaml
scheduler:
  enabled: true
  timezone: "America/New_York"
  schedules:
    - name: "yearly-recap"
      memory_type: "year_in_review"
      cron: "0 9 15 1 *"          # Jan 15 at 9am
      upload_to_immich: true
      album_name: "{year} Memories"

    - name: "monthly-highlights"
      memory_type: "monthly_highlights"
      cron: "0 9 1 * *"           # 1st of each month at 9am
      duration_minutes: 3

    - name: "on-this-day"
      memory_type: "on_this_day"
      cron: "0 9 * * *"           # Every day at 9am
      person_names: ["Alice"]

    - name: "summer-2024"
      memory_type: "season"
      cron: "0 9 1 10 *"          # Oct 1 at 9am
      enabled: false              # Paused
      params:
        season: "summer"
        year: 2024
```

Cron format: `minute hour day-of-month month day-of-week`. Standard 5-field cron syntax, nothing fancy.

## Scheduled birthdays, anniversaries, Mother's Day, and Father's Day

An event schedule can wake up every day and use `event_only: true` to generate only when the
selected logical subject or group actually occurs. This works for fixed birthdays and
anniversaries as well as floating rules such as the second Sunday in May. It avoids trying to
encode floating holidays into cron. `duration_minutes` is converted to the CLI's seconds.

These examples pull photos, Live Photos, and videos, assemble them chronologically, and upload
the completed memories:

```yaml
scheduler:
  enabled: true
  timezone: "America/Denver"
  schedules:
    - name: "Lucas birthday story"
      memory_type: "person_spotlight"
      cron: "0 8 * * *"           # Check every day at 8am
      event_only: true
      duration_minutes: 5
      upload_to_immich: true
      album_name: "Lucas Birthday Story"
      params:
        subject: lucas
        annual_story: true
        years_back: 20
        include_photos: true
        include_live_photos: true

    - name: "Anniversary story"
      memory_type: "multi_person"
      cron: "0 8 * * *"
      event_only: true
      duration_minutes: 10
      upload_to_immich: true
      album_name: "Anniversary Story"
      params:
        group: anniversary
        annual_story: true
        years_back: 20
        include_photos: true
        include_live_photos: true

    - name: "Mother's Day story"
      memory_type: "multi_person"
      cron: "0 8 * * *"
      event_only: true
      duration_minutes: 10
      upload_to_immich: true
      album_name: "Mother's Day Stories"
      params:
        group: mothers_day
        annual_story: true
        years_back: 20
        include_photos: true
        include_live_photos: true

    - name: "Father's Day story"
      memory_type: "multi_person"
      cron: "0 8 * * *"
      event_only: true
      duration_minutes: 10
      upload_to_immich: true
      album_name: "Father's Day Stories"
      params:
        group: fathers_day
        annual_story: true
        years_back: 20
        include_photos: true
        include_live_photos: true
```

The subject needs `birth_date`. A group needs either a fixed `event_date` or a floating
`event_rule`. Copy one guarded schedule for every child or other named event. On non-event days,
the guard exits without starting analysis or rendering.

Keep `immich-memories scheduler start --foreground` running for these entries. In Docker or
Unraid, run it as a second container using the same image, configuration volume, output volume,
network, API-key variables, and timezone as the UI container. It does not need a WebUI port.
