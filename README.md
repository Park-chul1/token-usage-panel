# Token Usage Panel

A GNOME 50 extension with **remaining Codex and Claude subscription quota** and **OpenAI API spending**.
A local reset button lets you track spending from a new reference point.
MIT licensed. Korean UI. Independent; not endorsed by OpenAI or GNOME.

## UI

- Codex: remaining %, small panel bar, and a separate additional-window percentage.
- Claude: remaining subscription percentage in the panel; five-hour and weekly windows in the menu.
- Menu: larger quota bars, countdowns and exact local reset times.
- Green above 30%; amber at 30% or less; red at 10% or less.
- Gray/warning for stale or failed snapshots. After expiry: `리셋 확인 중` until refreshed.
- API: this month's spend.
- Menu shows only this month's API spend.
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

API totals cover the key's whole organization and use UTC month boundaries.
Server reporting can be delayed. This is not a live billing meter or
credit-balance estimate; API refresh is cached for five minutes.

## Claude 구독 한도 연결

별도 Anthropic API 키나 유료 API 호출은 필요하지 않습니다. **Claude Code에 Claude 구독 계정으로 로그인**한 뒤, Claude Code가 공식 status line에 제공하는 한도 데이터를 이용합니다. 이 값은 남은 토큰 개수가 아니라 구독 사용 한도의 남은 **비율**입니다.

1. 이 확장 프로그램을 설치한 다음 Claude Code를 최신 버전으로 업데이트하고 구독 계정으로 로그인합니다.
2. `~/.claude/settings.json`에 아래 `statusLine` 항목을 추가합니다. 이미 다른 설정이 있다면 지우지 말고 JSON 객체 안에 항목만 추가하세요. `XDG_DATA_HOME`을 별도로 쓰는 경우 경로를 해당 설치 경로로 바꾸세요.

```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 \"$HOME/.local/share/gnome-shell/extensions/ai-usage@local/claude_status.py\""
  }
}
```

3. Claude Code를 다시 열고 대화에서 요청을 한 번 보내면, 응답 후 패널이 다음 갱신 때 한도를 표시합니다. Claude Code에서 한도 데이터가 제공되지 않으면 `확인 필요`로 표시됩니다. API 키 방식 로그인은 구독 한도를 제공하지 않습니다.

이미 `statusLine`을 사용 중이라면 위 설정으로 덮어쓰지 마세요. 기존 명령과 이 스크립트가 **같은 stdin JSON**을 각각 받도록 별도 래퍼를 만들어 연결해야 합니다.

이 방식은 Claude Code가 status line을 실행할 때만 갱신되므로, 종료 후 또는 웹에서만 사용하는 동안 최신 값이 아닐 수 있습니다. 5분이 지난 값은 회색과 `⚠`로 표시되고, 리셋 시각이 지나면 새 데이터가 도착할 때까지 `리셋 확인 중`으로 표시됩니다. 다중 계정을 번갈아 쓰면 마지막으로 데이터를 보낸 계정의 값이 표시됩니다. Claude Code의 지원 요금제 및 데이터 제공 조건은 [공식 문서](https://code.claude.com/docs/en/statusline)를 참고하세요.

스크립트는 입력 전체 중 사용률과 리셋 시각만 로컬 캐시에 저장합니다. 대화, 계정 인증 정보, API 키는 저장하거나 전송하지 않습니다. 사용량 한도는 Anthropic이 제공하는 정보이며, 확장이 별도로 Claude에 네트워크 요청을 보내지 않습니다.

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
