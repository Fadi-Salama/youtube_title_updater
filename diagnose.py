#!/usr/bin/env python3
"""
Health check: OBS stream key, YouTube channel identity, broadcasts, ingest
streams, and whether they line up. Run while OBS is streaming. ~5 quota units.
"""

import sys

from googleapiclient.errors import HttpError

from auto_title_updater import (OBS_HOST, OBS_PASSWORD, OBS_PORT, generate_title,
                      get_youtube_client, mask, normalise_key)

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except (AttributeError, ValueError):
    pass


def section(title: str) -> None:
    print(f'\n{"=" * 70}\n{title}\n{"=" * 70}')


def check_obs() -> tuple[str | None, bool]:
    section('1. OBS')
    try:
        from obsws_python import ReqClient
        client = ReqClient(host=OBS_HOST, port=OBS_PORT, password=OBS_PASSWORD)
    except Exception as exc:
        print(f'  ✗ Cannot connect to OBS at {OBS_HOST}:{OBS_PORT} -- {exc}')
        return None, False

    key, streaming = None, False
    try:
        version = client.get_version()
        print(f'  ✓ Connected. OBS {version.obs_version}, '
              f'websocket {version.obs_web_socket_version}')

        status = client.get_stream_status()
        streaming = bool(getattr(status, 'output_active', False))
        print(f'  streaming    : {streaming}')
        if streaming:
            print(f'  duration     : {getattr(status, "output_duration", 0) / 1000:.0f}s')
            print(f'  skipped frms : {getattr(status, "output_skipped_frames", "?")}')

        settings = client.get_stream_service_settings()
        values = getattr(settings, 'stream_service_settings', {}) or {}
        key = values.get('key')
        print(f'  service      : {getattr(settings, "stream_service_type", "?")}')
        print(f'  server       : {values.get("server")}')
        print(f'  key          : {mask(key)}')
        if not key:
            print('  ! No stream key. Switch OBS to Settings -> Stream -> '
                  '"Use Stream Key" instead of the linked-account integration.')
    except Exception as exc:
        print(f'  ! Error querying OBS: {exc}')
    finally:
        try:
            client.disconnect()
        except Exception:
            pass

    return key, streaming


def safe(label: str, request):
    print(f'\n--- {label} ---')
    try:
        return request.execute()
    except HttpError as error:
        print(f'  ✗ ERROR {getattr(error.resp, "status", "?")}: {error}')
        return None


def main() -> None:
    obs_key, obs_streaming = check_obs()

    section('2. YouTube')
    yt = get_youtube_client()

    channel_id = None
    r = safe('Who am I? (channels.list mine=True)',
             yt.channels().list(part='snippet', mine=True))
    if r:
        items = r.get('items', [])
        if not items:
            print('  ✗ No channel on this account. The token is probably for a '
                  'personal Google account, not the Brand Account that owns the '
                  'channel. Delete token.pickle and re-authorise.')
        for c in items:
            channel_id = c['id']
            print(f'  ✓ channelId : {c["id"]}')
            print(f'    title     : {c["snippet"]["title"]}')
            print(f'    customUrl : {c["snippet"].get("customUrl")}')

    matched_stream = None
    r = safe('Ingest stream keys (liveStreams.list mine=True)',
             yt.liveStreams().list(part='id,snippet,cdn,status',
                                   mine=True, maxResults=50))
    if r:
        items = r.get('items', [])
        print(f'  {len(items)} stream key(s)')
        for s in items:
            key = s.get('cdn', {}).get('ingestionInfo', {}).get('streamName')
            status = s.get('status', {})
            health = status.get('healthStatus', {}) or {}
            hit = obs_key and normalise_key(key) == normalise_key(obs_key)
            if hit:
                matched_stream = s
            print(f'  {"→" if hit else " "} {s["id"]}')
            print(f'      title  : {s["snippet"].get("title")}')
            print(f'      key    : {mask(key)}')
            print(f'      status : {status.get("streamStatus")} '
                  f'(health={health.get("status")})')
            for issue in health.get('configurationIssues', []) or []:
                print(f'      issue  : [{issue.get("severity")}] '
                      f'{issue.get("type")}: {issue.get("reason")}')

    r = safe('All broadcasts (liveBroadcasts.list mine=True, type=all)',
             yt.liveBroadcasts().list(part='snippet,status,contentDetails',
                                      mine=True, broadcastType='all',
                                      maxResults=50))
    live_now = []
    if r:
        items = r.get('items', [])
        print(f'  {len(items)} broadcast(s)')
        for b in sorted(items, key=lambda x: x['snippet'].get(
                'actualStartTime') or x['snippet'].get('scheduledStartTime') or '',
                reverse=True)[:15]:
            st, sn, cd = b['status'], b['snippet'], b.get('contentDetails', {})
            state = st.get('lifeCycleStatus')
            if state in ('live', 'testing', 'liveStarting'):
                live_now.append(b)
            print(f'  {b["id"]}  {state:<12} '
                  f'{sn.get("actualStartTime") or sn.get("scheduledStartTime")}')
            print(f'      title    : {sn.get("title")}')
            print(f'      bound    : {cd.get("boundStreamId")}  '
                  f'autoStart={cd.get("enableAutoStart")}  '
                  f'monitor={(cd.get("monitorStream") or {}).get("enableMonitorStream")}')

    section('3. VERDICT')
    print(f'Title right now: {generate_title()}')

    if not obs_streaming:
        print('• OBS is not streaming — start it, then rerun for a full picture.')
    if obs_key and matched_stream:
        st = matched_stream.get('status', {}).get('streamStatus')
        print(f'• ✓ OBS key matches YouTube stream {matched_stream["id"]} '
              f'(ingest status: {st}).')
        if st != 'active':
            print('  ! YouTube is NOT receiving data on it. Check the server URL '
                  '(should be rtmps://a.rtmps.youtube.com/live2) and the firewall.')
    elif obs_key:
        print('• ✗ The OBS key matches NO stream on this channel. OBS and the '
              'OAuth token are pointed at different channels.')
    else:
        print('• ✗ Could not read a stream key from OBS.')

    if live_now:
        for b in live_now:
            print(f'• Live now: {b["id"]} "{b["snippet"].get("title")}" '
                  f'-> https://www.youtube.com/watch?v={b["id"]}')
    else:
        print('• No broadcast is currently live.')


if __name__ == '__main__':
    main()