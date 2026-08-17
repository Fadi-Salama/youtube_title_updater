#!/usr/bin/env python3
"""
Manual rescue for a broadcast the bot could not drive live.

Usage:
    python unstick.py list                       # show all broadcasts (1 unit)
    python unstick.py <broadcastId>              # drive it live (default)
    python unstick.py <broadcastId> live
    python unstick.py <broadcastId> complete
    python unstick.py <broadcastId> delete
    python unstick.py cleanup                    # delete every stuck 'ready' one

Costs 1-150 quota units depending on the action.
"""

import sys
import time

from googleapiclient.errors import HttpError

from auto_title_updater import error_reasons, get_youtube_client

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except (AttributeError, ValueError):
    pass

LIVE_STATES = {'live', 'testing', 'liveStarting'}
READY_STATES = {'ready', 'created'}
ACTIONS = ('live', 'complete', 'delete', 'show')


def fetch(yt, broadcast_id: str) -> dict | None:
    """Return the broadcast resource, or None if it is not visible."""
    try:
        response = yt.liveBroadcasts().list(
            part='snippet,status,contentDetails', id=broadcast_id
        ).execute()
    except HttpError as error:
        if getattr(error.resp, 'status', None) == 404:
            return None
        raise
    items = response.get('items', [])
    return items[0] if items else None


def describe(b: dict) -> None:
    cd = b.get('contentDetails', {}) or {}
    sn = b.get('snippet', {})
    print(f'  lifecycle    : {b["status"].get("lifeCycleStatus")}')
    print(f'  privacy      : {b["status"].get("privacyStatus")}')
    print(f'  title        : {sn.get("title")}')
    print(f'  scheduled    : {sn.get("scheduledStartTime")}')
    print(f'  actualStart  : {sn.get("actualStartTime")}')
    print(f'  boundStreamId: {cd.get("boundStreamId")}')
    print(f'  autoStart    : {cd.get("enableAutoStart")}')
    print(f'  autoStop     : {cd.get("enableAutoStop")}')
    print(f'  monitorStream: '
          f'{(cd.get("monitorStream") or {}).get("enableMonitorStream")}')


def list_all(yt) -> list[dict]:
    response = yt.liveBroadcasts().list(
        part='snippet,status,contentDetails', mine=True,
        broadcastType='all', maxResults=50
    ).execute()
    items = response.get('items', [])

    if not items:
        print('  No broadcasts on this channel at all.')
        print('  If you expected some, the OAuth token is probably for the wrong')
        print('  Google account. Delete token.pickle and re-authorise as the')
        print('  Brand Account that owns the channel.')
        return []

    def when(b: dict) -> str:
        sn = b.get('snippet', {})
        return sn.get('actualStartTime') or sn.get('scheduledStartTime') or ''

    print(f'  {len(items)} broadcast(s), newest first:\n')
    print(f'  {"ID":<13} {"STATE":<12} {"BOUND":<6} {"WHEN":<22} TITLE')
    print(f'  {"-" * 13} {"-" * 12} {"-" * 6} {"-" * 22} {"-" * 30}')
    for b in sorted(items, key=when, reverse=True):
        cd = b.get('contentDetails', {}) or {}
        print(f'  {b["id"]:<13} '
              f'{b["status"].get("lifeCycleStatus", "?"):<12} '
              f'{"yes" if cd.get("boundStreamId") else "no":<6} '
              f'{when(b)[:22]:<22} '
              f'{b["snippet"].get("title", "")[:40]}')
    return items


def stream_active(yt, stream_id: str | None) -> bool:
    if not stream_id:
        print('  ingest       : (not bound to any stream)')
        return False
    items = yt.liveStreams().list(
        part='status', id=stream_id
    ).execute().get('items', [])
    if not items:
        print(f'  ingest       : stream {stream_id} not found')
        return False
    state = items[0]['status'].get('streamStatus')
    print(f'  ingest       : {state}')
    return state == 'active'


def transition(yt, broadcast_id: str, status: str) -> bool:
    try:
        result = yt.liveBroadcasts().transition(
            id=broadcast_id, part='id,status', broadcastStatus=status
        ).execute()
        print(f'  ✓ now {result["status"]["lifeCycleStatus"]}')
        return True
    except HttpError as error:
        print(f'  ✗ transition to {status} failed: '
              f'{", ".join(sorted(error_reasons(error))) or error}')
        return False


def disable_autostart(yt, broadcast_id: str, cd: dict) -> None:
    keep = ('enableAutoStop', 'enableDvr', 'enableEmbed', 'recordFromStart',
            'latencyPreference', 'projection', 'enableClosedCaptions')
    body_cd = {k: cd[k] for k in keep if cd.get(k) is not None}
    body_cd['enableAutoStart'] = False
    monitor = cd.get('monitorStream') or {}
    if monitor:
        body_cd['monitorStream'] = {
            'enableMonitorStream': monitor.get('enableMonitorStream', False),
            'broadcastStreamDelayMs': monitor.get('broadcastStreamDelayMs', 0),
        }
    yt.liveBroadcasts().update(
        part='id,contentDetails',
        body={'id': broadcast_id, 'contentDetails': body_cd},
    ).execute()
    print('  ✓ autostart disabled')


def go_live(yt, broadcast_id: str, b: dict) -> None:
    state = b['status'].get('lifeCycleStatus')
    cd = b.get('contentDetails', {}) or {}

    if state in LIVE_STATES:
        print(f'  Already {state}; nothing to do.')
        print(f'  Watch: https://www.youtube.com/watch?v={broadcast_id}')
        return
    if state == 'complete':
        print('  This broadcast has already finished; it cannot be restarted.')
        return
    if state == 'revoked':
        print('  This broadcast was revoked by YouTube (policy strike?).')
        return

    if not stream_active(yt, cd.get('boundStreamId')):
        print('  ! YouTube is not receiving video on the bound stream.')
        print('    Start OBS streaming to the bound key, then rerun.')
        return

    if cd.get('enableAutoStart'):
        print('  Disabling autostart (it blocks manual transitions)...')
        disable_autostart(yt, broadcast_id, cd)

    if (cd.get('monitorStream') or {}).get('enableMonitorStream'):
        print('  Monitor stream is on; going via "testing" first...')
        transition(yt, broadcast_id, 'testing')
        time.sleep(5)

    if transition(yt, broadcast_id, 'live'):
        print(f'\n  Watch: https://www.youtube.com/watch?v={broadcast_id}')


def cleanup(yt) -> None:
    """Delete every broadcast stuck in a pre-live state."""
    items = list_all(yt)
    stuck = [b for b in items
             if b['status'].get('lifeCycleStatus') in READY_STATES]
    if not stuck:
        print('\n  Nothing stuck in ready/created. Nothing to clean.')
        return

    print(f'\n  {len(stuck)} broadcast(s) never went live:')
    for b in stuck:
        print(f'    {b["id"]}  {b["snippet"].get("title", "")[:50]}')

    answer = input(f'\n  Delete all {len(stuck)}? [y/N] ').strip().lower()
    if answer != 'y':
        print('  Aborted.')
        return

    for b in stuck:
        try:
            yt.liveBroadcasts().delete(id=b['id']).execute()
            print(f'  ✓ deleted {b["id"]}')
        except HttpError as error:
            print(f'  ✗ {b["id"]}: {error}')


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    target = sys.argv[1]
    yt = get_youtube_client()

    if target == 'list':
        print('\nBroadcasts on this channel:')
        list_all(yt)
        return

    if target == 'cleanup':
        print('\nBroadcasts on this channel:')
        cleanup(yt)
        return

    action = (sys.argv[2] if len(sys.argv) > 2 else 'live').lower()
    if action not in ACTIONS:
        print(f'Unknown action "{action}". Use one of: {", ".join(ACTIONS)}')
        sys.exit(1)

    print(f'\nBroadcast {target}:')
    b = fetch(yt, target)

    if b is None:
        print('  ✗ Not found. It has been deleted, or it belongs to a different')
        print('    channel than this OAuth token.\n')
        print('  Broadcasts this token CAN see:')
        list_all(yt)
        sys.exit(1)

    describe(b)

    if action == 'show':
        return
    if action == 'delete':
        state = b['status'].get('lifeCycleStatus')
        if state in LIVE_STATES:
            answer = input(f'  ! This broadcast is {state}. Really delete? [y/N] ')
            if answer.strip().lower() != 'y':
                print('  Aborted.')
                return
        yt.liveBroadcasts().delete(id=target).execute()
        print('  ✓ deleted')
        return
    if action == 'complete':
        transition(yt, target, 'complete')
        return

    go_live(yt, target, b)


if __name__ == '__main__':
    main()