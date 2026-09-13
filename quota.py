"""Read quotas via the documented Codex app-server protocol; never start a turn."""
import json
import math
import os
import platform
from pathlib import Path
import select
import shutil
import signal
import subprocess
import time


def find_codex(config):
    explicit = config.get('codex_binary')
    if explicit:
        p = Path(explicit).expanduser()
        if not p.is_absolute() or not p.is_file() or not os.access(p, os.X_OK):
            raise FileNotFoundError('Invalid codex_binary')
        return str(p)
    found = shutil.which('codex')
    if found:
        return found
    candidates = []
    arch = {'x86_64': 'x86_64', 'aarch64': 'aarch64'}.get(platform.machine())
    if not arch:
        raise FileNotFoundError('Unsupported CPU architecture')
    for root in [Path.home()/'.vscode/extensions', Path.home()/'.vscode-insiders/extensions']:
        candidates.extend(root.glob(f'openai.chatgpt-*/bin/linux-{arch}/codex'))
    candidates = [p for p in candidates if p.is_file() and os.access(p, os.X_OK)]
    if candidates:
        return str(max(candidates, key=lambda p: p.stat().st_mtime_ns))
    raise FileNotFoundError('Codex CLI not found')


def fetch_limits(binary, cwd, timeout=18):
    proc = subprocess.Popen([binary, 'app-server'], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            cwd=cwd, start_new_session=True, bufsize=0)
    deadline, pending = time.monotonic()+timeout, b''
    def send(message):
        data = (json.dumps(message)+'\n').encode()
        while data:
            size = os.write(proc.stdin.fileno(), data)
            data = data[size:]
    def receive(identifier):
        nonlocal pending
        while time.monotonic() < deadline:
            while b'\n' in pending:
                line, pending = pending.split(b'\n', 1)
                try:
                    message = json.loads(line)
                except ValueError:
                    continue
                if message.get('id') == identifier:
                    if 'error' in message:
                        raise RuntimeError('Codex authentication or protocol error')
                    return message['result']
            ready, _, _ = select.select([proc.stdout], [], [], max(0, deadline-time.monotonic()))
            if not ready:
                break
            chunk = os.read(proc.stdout.fileno(), 65536)
            if not chunk:
                raise RuntimeError('Codex app-server exited')
            pending += chunk
            if len(pending) > 4*1024*1024:
                raise ValueError('Response too large')
        raise TimeoutError('Codex quota timeout')
    try:
        send({'id': 1, 'method': 'initialize', 'params': {'clientInfo': {
            'name': 'ai_usage_panel', 'title': 'AI Usage Panel', 'version': '0.2.0'}}})
        receive(1)
        send({'method': 'initialized'})
        send({'id': 2, 'method': 'account/rateLimits/read'})
        return receive(2)
    finally:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
        proc.stdin.close()
        proc.stdout.close()


def normalize(result):
    buckets = result.get('rateLimitsByLimitId') or {}
    if not buckets and result.get('rateLimits'):
        item = result['rateLimits']
        buckets = {item.get('limitId') or 'codex': item}
    normalized = []
    for name, bucket in buckets.items():
        windows = []
        for kind in ('primary', 'secondary'):
            w = bucket.get(kind)
            if not isinstance(w, dict):
                continue
            used, duration, reset = w.get('usedPercent'), w.get('windowDurationMins'), w.get('resetsAt')
            if isinstance(used, bool) or not isinstance(used, (int, float)) or not math.isfinite(used):
                continue
            if not isinstance(reset, (int, float)) or not math.isfinite(reset):
                continue
            windows.append({'kind': kind, 'remaining': max(0, min(100, 100-used)),
                            'minutes': duration, 'resets_at': reset})
        if windows:
            normalized.append({'id': name, 'name': bucket.get('limitName') or name, 'windows': windows})
    if not normalized:
        raise ValueError('No quota windows returned')
    normalized.sort(key=lambda b: (b['id'] != 'codex', b['id']))
    return normalized
