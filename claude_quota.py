"""Periodic subscription quota snapshots from Claude Code's local OAuth login.

The usage endpoint is undocumented and may change. Never refresh credentials or
write them to the cache; Claude Code remains responsible for its own login.
"""
import datetime as dt
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import time
import urllib.error
import urllib.request

INTERVAL = 6 * 3600
URL = 'https://api.anthropic.com/api/oauth/usage'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def credentials():
    root = Path(os.environ.get('CLAUDE_CONFIG_DIR', Path.home()/'.claude')).expanduser()
    with (root/'.credentials.json').open() as f:
        data = json.load(f)
    oauth = data.get('claudeAiOauth') or {}
    token = oauth.get('accessToken')
    if not isinstance(token, str) or not token or any(c.isspace() for c in token):
        raise ValueError('No Claude Code subscription login')
    expires = oauth.get('expiresAt')
    if isinstance(expires, (int, float)) and expires <= time.time()*1000:
        raise ValueError('Claude Code login expired')
    return token


def fetch(token):
    request = urllib.request.Request(URL, headers={
        'Authorization': 'Bearer '+token,
        'anthropic-beta': 'oauth-2025-04-20',
        'Accept': 'application/json',
    })
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(request, timeout=12) as response:
        payload = response.read(1024*1024+1)
    if len(payload) > 1024*1024:
        raise ValueError('Oversized response')
    return json.loads(payload)


def normalize(data, now):
    if not isinstance(data, dict):
        raise ValueError('Invalid response')
    windows = []
    for key, kind, minutes in [('five_hour', 'primary', 300), ('seven_day', 'secondary', 10080)]:
        item = data.get(key)
        if not isinstance(item, dict):
            continue
        used, reset = item.get('utilization'), item.get('resets_at')
        if isinstance(used, bool) or not isinstance(used, (int, float)) or not math.isfinite(used):
            continue
        try:
            parsed = dt.datetime.fromisoformat(reset.replace('Z', '+00:00'))
            if parsed.tzinfo is None:
                continue
            timestamp = parsed.timestamp()
        except (AttributeError, TypeError, ValueError, OverflowError):
            continue
        if timestamp <= now:
            continue
        windows.append({'kind': kind, 'remaining': max(0, min(100, 100-used)),
                        'minutes': minutes, 'resets_at': timestamp})
    if not windows:
        raise ValueError('No current subscription windows')
    return {'status': 'ok', 'updated': now,
            'buckets': [{'id': 'claude', 'name': 'Claude', 'windows': windows}]}


def poll(cache, read, save, force=False):
    """Poll every six hours, or on demand; never bypass a server rate limit."""
    now = time.time()
    cache.mkdir(parents=True, exist_ok=True, mode=0o700)
    # flock covers concurrent collector instances and protects the automatic schedule.
    fd = os.open(cache/'claude.lock', os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(fd, 'r+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        old = read(cache/'claude-poll.json', {})
        try:
            token = credentials()
            identity = hashlib.sha256(token.encode()).hexdigest()
        except (OSError, ValueError, TypeError):
            old.update(status='error', error='Claude Code 로그인 확인 필요')
            return old
        if old.get('identity') != identity:
            # A different token may mean a different account; never reuse old values.
            old = {'status': 'error', 'error': '로그인 변경 · 새 조회 대기',
                   'attempt': old.get('attempt', 0), 'blocked_until': old.get('blocked_until', 0),
                   'identity': identity}
            save(cache/'claude-poll.json', old)
        if now < old.get('blocked_until', 0):
            return old
        if not force and now - old.get('attempt', 0) < INTERVAL:
            return old
        try:
            result = normalize(fetch(token), now)
        except urllib.error.HTTPError as exc:
            result = dict(old, status='error', error='조회 제한 (HTTP 429)' if exc.code == 429 else '인증 또는 조회 실패 (HTTP %d)' % exc.code)
            if exc.code == 429:
                try:
                    retry = max(3600, int(exc.headers.get('Retry-After', '0')))
                except (AttributeError, ValueError, TypeError):
                    retry = 3600
                result['blocked_until'] = now + retry
        except Exception:
            result = dict(old, status='error', error='네트워크 또는 응답 확인 필요')
        result.update(attempt=now, identity=identity)
        save(cache/'claude-poll.json', result)
        return result
