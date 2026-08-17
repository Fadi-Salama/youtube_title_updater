# OBS → YouTube TitleBot

Creates and titles the YouTube live broadcast automatically when OBS starts
streaming, and ends it when OBS stops.

## Install

    pip install -r requirements.txt

Place `client_secret.json` (Google Cloud → APIs & Services → Credentials →
OAuth client ID → **Desktop app**) next to `titlebot.py`. The YouTube Data
API v3 must be enabled for that project.

## OBS setup (critical)

Settings → Stream:
- Service: **YouTube - RTMPS**
- Server: **Primary YouTube ingest server**
- **Use Stream Key** — paste the key from YouTube Studio.

Do **not** use "Connect Account". OBS's own YouTube integration creates its own
broadcast and will fight this bot for the stream key.

Settings → WebSocket Server: enabled, port `4457`, password matching
`OBS_PASSWORD` in `titlebot.py`.

## First run

    python preview_titles.py     # check the schedule renders correctly
    python titlebot.py           # authorise in the browser when prompted

At the Google consent screen pick the **Brand Account that owns the channel**,
not your personal account. If you pick wrong: delete `token.pickle` and rerun.

Then start streaming in OBS and watch `logs\titlebot.log`. Expected sequence:

    🔴 Stream STARTED detected.
    Target title: +++ Sunday Liturgy 17/08/2026 القداس الالهي +++
    No live broadcast found; creating one.
    Matched OBS stream key to YouTube stream J2MOTm6q8bS…
    🆕 Created broadcast XyZ123 (created, privacy=public) "…"
       autoStart=False autoStop=True monitorStream=False latency=low
    🔗 Bound broadcast XyZ123 to stream J2MOTm6q8bS…
    Ingest stream J2MOTm6q8bS…: active (health=good)
    ▶️  Transitioned XyZ123 -> live.
    ✅ Broadcast XyZ123 is live: https://www.youtube.com/watch?v=XyZ123

Test with `BROADCAST_PRIVACY = 'unlisted'` before going public.

## Running unattended

Task Scheduler → Create Task → "Run whether user is logged on or not" is **not**
suitable (OBS needs a desktop session). Use "Run only when user is logged on",
trigger *At log on*, action `run_titlebot.bat`, start-in set to this folder.

## Helper scripts

| Script | Purpose | Quota |
|---|---|---|
| `preview_titles.py`  | Print the week's titles; flag overlaps/overlength | 0  |
| `diagnose.py`        | OBS key ↔ YouTube stream ↔ broadcast health check | ~5 |
| `unstick.py cleanup` | Bulk-delete anything stuck at ready/created       | 1  |
| `unstick.py <id> [live\|complete\|delete]` | Manual rescue | 50–150 |

## Schedule

Edit `SERVICE_SCHEDULE` in `titlebot.py`. Each row is
`(weekday, (start_h, start_m), (end_h, end_m), title)` with Monday = 0, and
the window is `[start, end)` in **local time**. Outside every window the
generic title is used. Run `preview_titles.py` after any edit.

The Arabic suffix is chosen by keyword: `Liturgy` → القداس الالهي,
`Vespers`/`Venerations` → رفع بخور عشية, anything else → plain `+++`.

> **Note:** the Friday 10:00–17:30 entry
> `"+++ Vespers and Venerations for Saint Mary Testing new Title"` is a wide
> test window. Remove it once testing is done, or it will title any Friday
> daytime stream.

## Quota

YouTube allows 10,000 units/day, resetting at midnight **Pacific**. The bot
budgets 9,500 and stops before hitting the wall. A full service costs ~200
units (create 50 + bind 50 + transition 50 + complete 50 + a few list calls),
so ~45 services/day fit. `MAX_BROADCASTS_PER_DAY` (default 6) trips first.

`bot_state.json` holds the ledger, the cached broadcast/stream IDs and the last
applied title. Deleting it is safe — it only causes a little extra API traffic.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `Incompatible parameters: mine, broadcastStatus` | Old code. This version never sends that combination. |
| Broadcast stuck at `ready` | Ingest not active, or autostart blocked the transition. Run `diagnose.py`. |
| `invalidTransition` | `enableAutoStart` was true. This version creates with it false and disables it on inherited broadcasts. |
| `OBS key ... does not match any stream key` | OBS and the OAuth token are on different channels, or OBS uses the linked-account integration. |
| Two broadcasts appear | OBS "Connect Account" is on. Switch to a stream key. |
| Nothing happens on stream start | Check the WebSocket port/password; look for `Connected to OBS WebSocket` in the log. |