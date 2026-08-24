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
```

Open Immich while signed in as each owner, open a person, and copy the UUID from that person's
page URL. Person IDs are account-specific even when both owners call the face “Lucas.”

The primary account must have Partner Sharing access to Katie's assets so it can download every
result after Katie's private face search finds it. Shared duplicates are removed by checksum.

## 4. Generate

Restart the container after editing the YAML, open its WebUI, and choose:

- **Monthly Highlights → Cross-account people → The Kids (ANY)** for Asher OR Lucas OR Charles.
- **Multi-Person → Michael & Katie (ALL)** for assets where both appear together.
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

The advanced scheduler can run these commands annually. See the scheduler documentation for
ready-to-paste birthday and anniversary cron entries.

The first target is five minutes and the second is ten. Title cards and transition overlap are
part of that budget, so the encoded runtime can differ slightly from the requested target.
