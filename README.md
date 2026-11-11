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

Claude Code를 설치하고 Claude **Pro/Max 구독 계정으로 로그인**하세요. 별도 유료 API 키는 필요하지 않습니다. 확장 프로그램이 켜져 있는 동안 Claude 구독의 5시간 및 주간 남은 한도를 약 6시간마다 조회합니다. 메뉴의 **Claude 사용량 업데이트** 버튼을 누르면 추가로 조회합니다. 화면 표시는 60초마다 갱신됩니다. 숫자는 남은 토큰 개수가 아닌 사용 한도의 **비율**입니다. 계정 또는 요금제에 따라 일부 한도는 제공되지 않을 수 있습니다.

이 조회는 Claude Code의 로컬 로그인 파일(`~/.claude/.credentials.json`, 또는 `CLAUDE_CONFIG_DIR` 아래)을 읽어 Anthropic의 **문서화되지 않은** 사용량 엔드포인트에 인증 요청을 보냅니다. 서버가 이를 변경하거나 제한하면 동작하지 않을 수 있으며, Anthropic의 [인증 가이드](https://code.claude.com/docs/en/legal-and-compliance)를 확인하세요. API 키/Console 계정 로그인이 아닌 구독 계정 로그인이 필요합니다. 로그인 파일이 없거나 인증이 만료되면 Claude Code에서 다시 로그인하세요. 패널은 인증 토큰을 갱신하지 않습니다.

조회 오류 및 429 응답은 마지막 정상 값을 경고와 함께 표시하고 자동으로는 6시간 후 재시도합니다. 429 응답이 오면 버튼을 눌러도 최소 1시간 또는 서버가 지정한 시간 동안 재조회하지 않습니다. 리셋 시각이 지나면 새 응답을 받을 때까지 `리셋 확인 중`이라고 표시합니다. 일반 새로고침은 Claude 조회를 강제하지 않습니다. 컴퓨터가 꺼졌거나 확장 프로그램이 비활성화된 동안에는 조회하지 않습니다.

사용량 스냅샷과 인증 토큰의 해시(계정 전환 감지용)만 로컬 캐시에 저장합니다. 토큰 원문, 대화 내용, 응답 원문은 저장하거나 출력하지 않습니다. 토큰은 Anthropic의 고정 HTTPS 주소로만 전송하며 리다이렉트를 따르지 않습니다. 조회 자체는 모델 대화를 시작하거나 모델 추론 토큰을 사용하지 않습니다.

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
