#!/usr/bin/env python3
"""Local Codex metadata + organization OpenAI usage. No conversation uploads."""
import datetime as dt
import decimal
import getpass
import hashlib
import concurrent.futures
import tempfile
import quota
import json
import os
from pathlib import Path
import sys
import time
import urllib.request
import urllib.parse
import urllib.error

CONFIG = Path(os.environ.get('XDG_CONFIG_HOME', Path.home()/'.config'))/'ai-usage-panel'
CACHE = Path(os.environ.get('XDG_CACHE_HOME', Path.home()/'.cache'))/'ai-usage-panel'
FIELDS = ('input_tokens', 'output_tokens', 'cached_input_tokens')

def read(path, default):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(prefix=path.name+'.', dir=path.parent)
    tmp = Path(name)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(value, f)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def parse_log(path):
    previous = dict.fromkeys(FIELDS, 0)
    days, session, warnings = {}, None, 0
    with path.open() as stream:
        for line in stream:
            try:
                event = json.loads(line)
                payload = event.get('payload') or {}
                if event.get('type') == 'session_meta':
                    session = payload.get('id', session)
                if event.get('type') != 'event_msg' or payload.get('type') != 'token_count':
                    continue
                total = (payload.get('info') or {}).get('total_token_usage')
                if not total:
                    continue
                current = {k: int(total.get(k, 0)) for k in FIELDS}
                stamp = dt.datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00'))
                day = stamp.astimezone().date().isoformat()
                # A decrease is ambiguous (reset/compaction/schema change): do not invent usage.
                delta = {k: max(0, current[k]-previous[k]) for k in FIELDS}
                if any(current[k] < previous[k] for k in FIELDS):
                    warnings += 1
                    delta = dict.fromkeys(FIELDS, 0)
                previous = current
                row = days.setdefault(day, dict.fromkeys(FIELDS, 0))
                for k in FIELDS:
                    row[k] += delta[k]
            except (ValueError, TypeError, KeyError):
                warnings += 1
    return {'session': session or str(path), 'days': days, 'warnings': warnings}

def codex():
    root = Path(os.environ.get('CODEX_HOME', Path.home()/'.codex'))
    index = read(CACHE/'logs.json', {})
    fresh, sessions, errors = {}, {}, 0
    paths = sorted(set(root.glob('sessions/**/*.jsonl')) | set(root.glob('archived_sessions/**/*.jsonl')))
    for path in paths:
        try:
            st = path.stat()
            signature = [st.st_size, st.st_mtime_ns]
            item = index.get(str(path), {})
            if item.get('signature') != signature:
                item = {'signature': signature, **parse_log(path)}
            fresh[str(path)] = item
            old = sessions.get(item['session'])
            if not old or sum(v['input_tokens'] for v in item['days'].values()) > sum(v['input_tokens'] for v in old['days'].values()):
                sessions[item['session']] = item
        except OSError:
            errors += 1
    save(CACHE/'logs.json', fresh)
    today = dt.datetime.now().date()
    monday = today-dt.timedelta(days=today.weekday())
    result = {'today': dict.fromkeys(FIELDS, 0), 'week': dict.fromkeys(FIELDS, 0), 'files': len(paths), 'warnings': errors}
    for item in sessions.values():
        result['warnings'] += item['warnings']
        for date, row in item['days'].items():
            for period, match in [('today', date == today.isoformat()), ('week', monday.isoformat() <= date <= today.isoformat())]:
                if match:
                    for k in FIELDS:
                        result[period][k] += row[k]
    result['status'] = 'ok' if paths else 'no_logs'
    return result

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

def query(endpoint, key, start, end, **extra):
    params = {'start_time': int(start), 'end_time': int(end), 'bucket_width': '1d', 'limit': 31, **extra}
    rows, pages = [], set()
    opener = urllib.request.build_opener(NoRedirect)
    for _ in range(100):
        url = 'https://api.openai.com/v1/organization/'+endpoint+'?'+urllib.parse.urlencode(params, doseq=True)
        req = urllib.request.Request(url, headers={'Authorization': 'Bearer '+key})
        with opener.open(req, timeout=15) as response:
            data = json.load(response)
        rows.extend(r for b in data['data'] for r in b['results'])
        if not data.get('has_more'):
            return rows
        page = data.get('next_page')
        if not page or page in pages:
            raise ValueError('Invalid pagination')
        pages.add(page)
        params['page'] = page
    raise ValueError('Too many pages')

def get_key():
    keyfile = CONFIG/'admin-key'
    if keyfile.stat().st_mode & 0o077:
        raise PermissionError('Key permissions')
    return keyfile.read_text().strip()


def key_id(key):
    return hashlib.sha256(key.encode()).hexdigest()


def cost_sum(key, start, end):
    rows = query('costs', key, start, end)
    if any(r['amount']['currency'].lower() != 'usd' for r in rows):
        raise ValueError('Unexpected currency')
    value = sum((decimal.Decimal(str(r['amount']['value'])) for r in rows), decimal.Decimal(0))
    if not value.is_finite():
        raise ValueError('Invalid amount')
    return value


def api(force=False):
    if not (CONFIG/'admin-key').exists():
        return {'status': 'unconfigured'}
    baseline = read(CONFIG/'api-reset.json', {})
    old = read(CACHE/'api.json', {})
    now = time.time()
    try:
        key = get_key()
        identity = key_id(key)
        if baseline.get('key_id') != identity:
            baseline = {}
        if old.get('reset_id') != baseline.get('id') or old.get('key_id') != identity:
            old = {}
        if not force and now-old.get('attempt', 0) < 300:
            return old
        utc = dt.datetime.now(dt.timezone.utc)
        month = utc.replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp()
        today = utc.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        month_cost = cost_sum(key, month, now)
        today_cost = cost_sum(key, today, now)
        result = {'status': 'ok', 'month_usd': float(month_cost), 'today_usd': float(today_cost),
                  'updated': now, 'key_id': identity, 'reset_id': baseline.get('id'),
                  'display_usd': float(month_cost), 'display_period': 'month', 'models': {}}
        if baseline:
            # Query the same start date, including across month boundaries.
            total = cost_sum(key, baseline['start'], now)
            result.update(display_usd=float(total-decimal.Decimal(baseline['cost_usd'])),
                          display_period='since_reset', reset_at=baseline['recorded_at'])
        for row in query('usage/completions', key, month, now, **{'group_by': ['model']}):
            name = row.get('model') or 'unknown'
            value = result['models'].setdefault(name, {'input': 0, 'output': 0, 'cached': 0})
            for dest, src in [('input','input_tokens'), ('output','output_tokens'), ('cached','input_cached_tokens')]:
                value[dest] += row.get(src, 0)
        old = result
    except urllib.error.HTTPError as exc:
        old.update(status='error', error='HTTP '+str(exc.code))
    except PermissionError:
        old.update(status='error', error='Key file permissions: chmod 600')
    except Exception:
        old.update(status='error', error='Network or response error')
    old['attempt'] = now
    save(CACHE/'api.json', old)
    return old


def reset_api():
    """Rebase the displayed cost counter only after a successful fresh API read."""
    try:
        key = get_key()
        now = time.time()
        start = dt.datetime.now(dt.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        total = cost_sum(key, start, now)
        baseline = {'id': str(time.time_ns()), 'cost_usd': str(total), 'start': start,
                    'recorded_at': now, 'key_id': key_id(key)}
        save(CONFIG/'api-reset.json', baseline)
        (CACHE/'api.json').unlink(missing_ok=True)
        return {'ok': True}
    except Exception:
        return {'ok': False, 'error': 'API 조회 실패 · 이전 표시 기준 유지'}


def quotas(force=False):
    now = time.time()
    old = read(CACHE/'quota.json', {})
    if not force and now-old.get('attempt', 0) < 60:
        return old
    try:
        binary = quota.find_codex(read(CONFIG/'settings.json', {}))
        CACHE.mkdir(parents=True, exist_ok=True, mode=0o700)
        with tempfile.TemporaryDirectory(prefix='quota-', dir=CACHE) as neutral:
            buckets = quota.normalize(quota.fetch_limits(binary, neutral))
        old = {'status': 'ok', 'buckets': buckets, 'updated': now}
    except FileNotFoundError:
        old.update(status='error', error='Codex CLI not found; see README')
    except TimeoutError:
        old.update(status='error', error='Codex quota request timed out')
    except Exception:
        old.update(status='error', error='Codex login / app-server response error')
    old['attempt'] = now
    save(CACHE/'quota.json', old)
    return old


if __name__ == '__main__':
    os.umask(0o077)
    if '--set-key' in sys.argv:
        key = getpass.getpass('OpenAI Admin API key (hidden): ').strip()
        if not key or any(c.isspace() for c in key):
            sys.exit('Empty or invalid key; nothing saved.')
        CONFIG.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(CONFIG/'admin-key', os.O_WRONLY|os.O_CREAT|os.O_TRUNC, 0o600)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w') as f:
            f.write(key)
        for path in [CACHE/'api.json', CONFIG/'api-reset.json']:
            path.unlink(missing_ok=True)
        print('Key saved locally. Refresh the panel.')
    elif '--reset-api' in sys.argv:
        print(json.dumps(reset_api()))
    elif '--monthly-api' in sys.argv:
        (CONFIG/'api-reset.json').unlink(missing_ok=True)
        (CACHE/'api.json').unlink(missing_ok=True)
        print(json.dumps({'ok': True}))
    elif '--tokens' in sys.argv:
        print(json.dumps(codex()))
    else:
        force = '--refresh-api' in sys.argv or '--refresh' in sys.argv
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            q, a = pool.submit(quotas, force), pool.submit(api, force)
            print(json.dumps({'quota': q.result(), 'api': a.result(), 'updated': time.time()}))
