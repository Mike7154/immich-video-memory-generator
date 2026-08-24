---
title: Unraid multi-account fork
---

# Install the multi-account fork on Unraid

The Unraid **Add Container** page can run an image but cannot build source code. Publish this fork
to your own GitHub Container Registry first; the included workflow builds the image for you.

## 1. Publish the fork image

1. Fork the repository on GitHub and push the `feat/multi-account-subjects` branch.
2. Open **Actions → Multi-account container image → Run workflow**.
3. Wait for the green check, then open the new package on your GitHub profile and set its
   visibility to **Public**. For a private package, log Unraid's Docker daemon into `ghcr.io`
   instead.
4. Your image repository is
   `ghcr.io/YOUR-LOWERCASE-GITHUB-NAME/immich-video-memory-generator:multi-account`.

## 2. Add the container

In Unraid, open **Docker → Add Container**, enable Advanced View if needed, and enter:

| Field | Value |
|---|---|
| Name | `Immich-Memories-Family` |
| Repository | the `ghcr.io/...:multi-account` image above |
| Network Type | `Bridge` |
| WebUI | `http://[IP]:[PORT:8080]` |
| Container Port | `8080` (choose any unused host port, such as `8088`) |
| Config path | `/mnt/user/appdata/immich-memories` → `/home/immich/.immich-memories` |
| Output path | `/mnt/user/Media/Immich Memories` → `/app/output` |

Add these variables. Mark all three API keys as password/secret fields in the template:

| Variable | Example |
|---|---|
| `IMMICH_URL` | `http://192.168.50.111:2283` |
| `IMMICH_API_KEY` | Michael's key; this is the render/upload account |
| `MICHAEL_IMMICH_API_KEY` | Michael's discovery key |
| `KATIE_IMMICH_API_KEY` | Katie's discovery key |
| `TZ` | `America/Denver` |
| `IMMICH_MEMORIES_AUTH_USERNAME` | a local username |
| `IMMICH_MEMORIES_AUTH_PASSWORD` | a strong password |

If Immich is not published on port 2283, use the same reachable URL you use from another LAN
device. Alternatively put this container on Unraid's `immich_default` custom network and use the
Immich server container's DNS name. Do not publish the UI without authentication: it holds keys
that can read the family photo library.

For each account key, **All permissions** is the reliable choice. The minimal discovery set is
read access to people, assets, timeline, and search. The primary key also needs asset upload and
album create/update when generated videos should be sent back to Immich.

## 3. Add the identity map

Start the container once, then edit
`/mnt/user/appdata/immich-memories/config.yaml`. Keep the existing `immich:` section and add:

```yaml
identities:
  accounts:
    michael:
      api_key: "${MICHAEL_IMMICH_API_KEY}"
    katie:
      api_key: "${KATIE_IMMICH_API_KEY}"
  subjects:
    michael:
      display_name: "Michael"
      people:
        michael: "MICHAEL-ID-IN-MICHAELS-ACCOUNT"
        katie: "MICHAEL-ID-IN-KATIES-ACCOUNT"
    katie:
      display_name: "Katie"
      people:
        michael: "KATIE-ID-IN-MICHAELS-ACCOUNT"
        katie: "KATIE-ID-IN-KATIES-ACCOUNT"
    asher:
      display_name: "Asher"
      people:
        michael: "ASHER-ID-IN-MICHAELS-ACCOUNT"
        katie: "ASHER-ID-IN-KATIES-ACCOUNT"
    lucas:
      display_name: "Lucas"
      birth_date: 2018-04-10
      people:
        michael: "LUCAS-ID-IN-MICHAELS-ACCOUNT"
        katie: "LUCAS-ID-IN-KATIES-ACCOUNT"
    charles:
      display_name: "Charles"
      people:
        michael: "CHARLES-ID-IN-MICHAELS-ACCOUNT"
        katie: "CHARLES-ID-IN-KATIES-ACCOUNT"
  groups:
    kids:
      display_name: "The Kids"
      subjects: [asher, lucas, charles]
      match: any
    anniversary:
      display_name: "Michael & Katie"
      subjects: [michael, katie]
      match: all
      event_date: 2012-09-22
    mothers_day:
      display_name: "Mom & Kids"
      required: [katie]
      any_of: [asher, lucas, charles]
      event_rule:
        month: 5
        weekday: sunday
        occurrence: 2
    fathers_day:
      display_name: "Dad & Kids"
      required: [michael]
      any_of: [asher, lucas, charles]
      event_rule:
        month: 6
        weekday: sunday
        occurrence: 3
```

Open Immich while signed in as each owner, open a person, and copy the UUID from that person's
page URL. Person IDs are account-specific even when both owners call the face “Lucas.”

The primary account must have Partner Sharing access to Katie's assets so it can download every
result after Katie's private face search finds it. Shared duplicates are removed by checksum.

## 4. Generate

Restart the container after editing the YAML, open its WebUI, and choose:

- **Monthly Highlights → Cross-account people → The Kids (ANY)** for Asher OR Lucas OR Charles.
- **Multi-Person → Michael & Katie (ALL)** for assets where both appear together.
- **Multi-Person → Mom & Kids (REQUIRED + ANY)** for Katie with at least one child.
- **Multi-Person → Dad & Kids (REQUIRED + ANY)** for Michael with at least one child.
- **Person Spotlight → Lucas (all accounts)** for a birthday memory.

In Step 2, turn **Auto duration** off and set **Target duration (min)**. On the CLI, use seconds:

```bash
immich-memories generate --group kids --year 2026 --month 7 --duration 300 \
  --include-photos --include-live-photos --upload-to-immich --album "Kids - July 2026"

immich-memories generate --group anniversary --year 2025 --duration 600 \
  --upload-to-immich --album "Anniversary 2025"
```

For the annual birthday/anniversary format requested here, add `--annual-story`. This includes
historical occurrences of the event date and the year ending on the selected occurrence, and
assembles the chosen photos and video clips chronologically:

```bash
immich-memories generate --subject lucas --annual-story --year 2026 \
  --years-back 20 --duration 300 --include-photos --include-live-photos \
  --upload-to-immich --album "Lucas Birthday Story 2026"

immich-memories generate --group anniversary --annual-story --year 2026 \
  --years-back 20 --duration 600 --include-photos --include-live-photos \
  --upload-to-immich --album "Anniversary Story 2026"
```

## 5. Run family events automatically

Add the ready-to-paste guarded schedules from the scheduler documentation to `config.yaml`.
Each schedule checks daily, while `event_only: true` prevents it from rendering except on the
configured birthday, anniversary, Mother's Day, Father's Day, or other event.

Create a second Unraid container from the same image for the scheduler:

1. Use a different name, such as `Immich-Memories-Scheduler`.
2. Reuse the UI container's network, API-key variables, timezone, config mapping, and output
   mapping.
3. Do not map port 8080.
4. In Advanced View, add `--no-healthcheck` to **Extra Parameters**, because this container does
   not run the UI health endpoint.
5. Set **Post Arguments** to:

   ```text
   immich-memories scheduler start --foreground
   ```

Keep both containers running. The UI container remains the editor and manual generator; the
scheduler container performs the recurring event checks. Both can continue pulling
`ghcr.io/mike7154/immich-video-memory-generator:multi-account` through Unraid auto-update.

The first target is five minutes and the second is ten. Title cards and transition overlap are
part of that budget, so the encoded runtime can differ slightly from the requested target.
