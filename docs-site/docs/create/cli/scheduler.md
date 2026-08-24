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

## Scheduled cross-account birthday and anniversary stories

Logical subjects and groups can run automatically on their event dates. `duration_minutes` is
converted to the CLI's seconds internally. These examples pull photos, Live Photos, and videos,
then upload the chronological result:

```yaml
scheduler:
  enabled: true
  timezone: "America/Denver"
  schedules:
    - name: "Lucas birthday story"
      memory_type: "person_spotlight"
      cron: "0 8 10 4 *"          # April 10 at 8am
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
      cron: "0 8 22 9 *"          # September 22 at 8am
      duration_minutes: 10
      upload_to_immich: true
      album_name: "Anniversary Story"
      params:
        group: anniversary
        annual_story: true
        years_back: 20
        include_photos: true
        include_live_photos: true
```

The subject needs `birth_date`; the group needs `event_date` and normally uses `match: all` for an
anniversary. Keep `scheduler start --foreground` running in the container for these cron entries.
