#!/usr/bin/env python3
"""Claude Code status line: save only subscription limit percentages and resets."""
import json
import math
import os
from pathlib import Path
import tempfile
import time

CACHE = Path(os.environ.get('XDG_CACHE_HOME', Path.home()/'.cache'))/'ai-usage-panel'


def normalize(data, now):
    limits = data.get('rate_limits')
    if not isinstance(limits, dict):
        return None
    windows = []
    for key, kind, minutes in [('five_hour', 'primary', 300), ('seven_day', 'secondary', 10080)]:
        item = limits.get(key)
        if not isinstance(item, dict):
            continue
        used, reset = item.get('used_percentage'), item.get('resets_at')
        if (isinstance(used, bool) or not isinstance(used, (int, float)) or not math.isfinite(used)
                or isinstance(reset, bool) or not isinstance(reset, (int, float))
                or not math.isfinite(reset) or reset <= now):
            continue
        windows.append({'kind': kind, 'remaining': max(0, min(100, 100-used)),
                        'minutes': minutes, 'resets_at': reset})
    if not windows:
        return None
    return {'status': 'ok', 'updated': now,
            'buckets': [{'id': 'claude', 'name': 'Claude', 'windows': windows}]}


def save(snapshot):
    CACHE.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(prefix='claude.', dir=CACHE)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(snapshot, f)
        os.replace(name, CACHE/'claude.json')
    finally:
        Path(name).unlink(missing_ok=True)


def main():
    os.umask(0o077)
    try:
        data = json.load(__import__('sys').stdin)
        snapshot = normalize(data, time.time()) if isinstance(data, dict) else None
        if snapshot:
            save(snapshot)
            parts = [f"{int(w['remaining'])}%" for w in snapshot['buckets'][0]['windows']]
            print('Claude 남음 ' + ' / '.join(parts))
        else:
            print('Claude 한도 확인 중')
    except (OSError, ValueError, TypeError):
        print('Claude 한도 확인 필요')


if __name__ == '__main__':
    main()
