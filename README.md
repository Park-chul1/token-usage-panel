# Token Usage Panel

A GNOME 50 extension with **remaining Codex quota bars** and **OpenAI API spending**.
A local reset button lets you track spending from a new reference point.
MIT licensed. Korean UI. Independent; not endorsed by OpenAI or GNOME.

## UI

- Codex: remaining %, small panel bar, and a separate additional-window percentage.
- Menu: larger quota bars, countdowns and exact local reset times.
- Green above 30%; amber at 30% or less; red at 10% or less.
- Gray/warning for stale or failed snapshots. After expiry: `리셋 확인 중` until refreshed.
- API: monthly spend by default. After reset: `API ↺ $0.00` and subsequent costs.
- Menu always retains today's and this month's full spend and model token breakdown.
- Bars are read-only indicators, not draggable controls.

## Requirements

GNOME 50, Python 3.10+, a local authenticated Codex installation for quota data.
Only Python's standard library is used at runtime. No pip/npm install required.
API spending additionally requires an OpenAI Admin API key with usage access.

## Install / upgrade

처음 설치할 때는 저장소를 복제합니다:

```bash
git clone https://github.com/Park-chul1/token-usage-panel.git
cd token-usage-panel
```

복제한 폴더 또는 압축을 푼 소스 폴더에서:

```bash
bash install.sh
```

기존 버전 위에 설치해도 API 키는 유지됩니다. 작업을 저장하고 로그아웃/로그인
또는 재부팅 후 실행하세요:

```bash
gnome-extensions enable ai-usage@local
```

Installed under `$XDG_DATA_HOME/gnome-shell/extensions/ai-usage@local`, defaulting
to `~/.local/share/gnome-shell/extensions/ai-usage@local`.
The source directory can be anywhere; the installer copies the required files.

## API connection

Already connected in v1? Your key is retained; no extra balance setup is needed.
For a new connection create an Admin key in the correct organization:
https://platform.openai.com/settings/organization/admin-keys

```bash
python3 ~/.local/share/gnome-shell/extensions/ai-usage@local/collector.py --set-key
```

Paste the key into the hidden prompt and refresh the panel. If using a custom
XDG_DATA_HOME, adjust the path above. Regular model-inference keys may not have
permission to read organization usage/costs.

### Reset button

Click **API 표시 사용량 초기화** in the panel menu. The collector first fetches a
fresh cost total and records it as the reference; subsequent display values are
the difference from that total. A failed request leaves the previous reference
intact. The counter works across month boundaries. Choose **이번 달 사용 금액으로
돌아가기** to restore monthly display. Equivalent local commands:

```bash
python3 ~/.local/share/gnome-shell/extensions/ai-usage@local/collector.py --reset-api
python3 ~/.local/share/gnome-shell/extensions/ai-usage@local/collector.py --monthly-api
```

**Reset changes only this tool's displayed cost counter. It does not change API
billing records, credits, or Codex limits.** Model token rows remain monthly totals.
API totals cover the key's whole organization. Today/month periods use UTC.
Server reporting can be delayed: costs reported after reset can include earlier
requests. Corrections may make a counter negative. This is not a live billing
meter or credit-balance estimate. API refresh is cached for five minutes.

## Codex quota source

The documented `codex app-server` method `account/rateLimits/read` supplies
`usedPercent`, `windowDurationMins`, and `resetsAt`. Remaining = 100 − usedPercent.
There is no invented daily token maximum: labels reflect the actual server window
(e.g. five hours and weekly). Model-specific buckets are kept separate.

Every 60 seconds, the collector initializes an app-server connection from a neutral
temporary directory, reads rate limits, and terminates the process. No model turn,
thread, email, credit purchase or quota reset is requested. API-key-only Codex login
may not return ChatGPT subscription limits. Errors retain visibly marked old values.
An expired window never becomes 100% without a fresh server response.

The collector finds `codex` on PATH or the Linux binary shipped in the official
VS Code OpenAI extension. If it cannot find it, create
`~/.config/ai-usage-panel/settings.json`:

```json
{"codex_binary": "/absolute/path/to/codex"}
```

Use your installed binary and authenticate it normally. The panel does not ask
for your ChatGPT password. Custom CODEX_HOME must be available to the GNOME session,
not just an interactive shell. Settings/cache honor XDG_CONFIG_HOME/XDG_CACHE_HOME.

## Git updates

From a Git clone of this source:

```bash
bash update.sh
```

This refuses local uncommitted changes, runs `git pull --ff-only`, and installs.
Log out/in to reload GNOME JavaScript. Updates are manual. Keys, counters, and
caches remain outside the repository and are preserved during installation.

## Development and validation

```bash
python3 -m unittest discover -v
node --test test_model.js
node --check extension.js
bash -n install.sh update.sh
```

Node is used only for tests. Tests cover quota normalization, protocol handshake
without model turns, timeouts, reset failures, separate monthly/reset totals,
key changes, pagination and stale/expired UI states. Synthetic fixtures only.
GNOME 50 rendering and live account authentication still require verification on
a GNOME desktop. The installer was checked with an isolated GNOME-command stub.

Legacy local token totals remain available with `collector.py --tokens`, but never
supply the remaining %. This optional parser may undercount cumulative-counter
resets or double-count forked histories with different session IDs.

## Privacy and credentials

The Admin key is stored at `~/.config/ai-usage-panel/admin-key` with mode 0600,
**plaintext, without OS-keyring encryption**. Settings and aggregate caches live
outside the repo. Keys go only to the official OpenAI API; Codex uses its own
app-server authentication. No third-party telemetry or conversation uploads.
Never commit keys, auth files, account responses or JSONL logs. `.gitignore`
excludes common secret/cache filenames as an additional precaution.

## Diagnostics and removal

```bash
python3 ~/.local/share/gnome-shell/extensions/ai-usage@local/collector.py --refresh
gnome-extensions info ai-usage@local
```

Diagnostics print aggregate values, never keys. To remove:

```bash
gnome-extensions disable ai-usage@local
gnome-extensions uninstall ai-usage@local
```

Config/cache directories are retained. Delete their `ai-usage-panel` subdirectory
separately to also remove credentials and local counters.

## Contributing / license

MIT — see LICENSE. Include GNOME/Codex versions and expected versus observed
behavior in bug reports. Run tests before a PR. Do not include credentials or
real session logs. GitHub Actions runs the offline test suite.

## References

- https://learn.chatgpt.com/docs/app-server#6-rate-limits-chatgpt
- https://developers.openai.com/api/reference/resources/admin/subresources/organization/subresources/usage/methods/costs
- https://gjs.guide/extensions/development/creating.html
- https://gjs.guide/extensions/upgrading/gnome-shell-50.html
