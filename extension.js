import St from 'gi://St';
import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import {duration, windowState, resetText, apiText} from './model.js';

function label(text, style = '') {
    return new St.Label({text, y_align: Clutter.ActorAlign.CENTER, style});
}
function meter(width, height = 6) {
    // A horizontal box anchors the fill at the leading edge; BinLayout can
    // center a non-expanding child regardless of its requested x alignment.
    const track = new St.BoxLayout({
        width, height, x_expand: false, y_expand: false,
        y_align: Clutter.ActorAlign.CENTER,
        style: `background-color: #39414c; border-radius: ${height/2}px; padding: 0; spacing: 0;`});
    const fill = new St.Widget({width: 0, height,
        x_expand: false, y_expand: false,
        x_align: Clutter.ActorAlign.START, y_align: Clutter.ActorAlign.CENTER});
    track.add_child(fill);
    return {track, fill, width, height};
}
function paint(bar, state) {
    bar.fill.visible = state.known && state.value > 0;
    bar.fill.width = state.known ? bar.width * state.value/100 : 0;
    bar.fill.style = `background-color: ${state.color}; border-radius: ${bar.height/2}px;`;
}
export default class AIUsage extends Extension {
    enable() {
        this._button = new PanelMenu.Button(0.0, 'AI Usage: remaining allowance and API spending', false);
        const box = new St.BoxLayout({y_align: Clutter.ActorAlign.CENTER,
            style: 'spacing: 8px;'});
        this._quotaLabel = label('Codex …');
        this._bar = meter(64);
        this._weekly = label('');
        this._apiLabel = label('API …');
        for (const widget of [this._quotaLabel, this._bar.track, this._weekly, label('│', 'color: #738090;'), this._apiLabel])
            box.add_child(widget);
        this._button.add_child(box);
        Main.panel.addToStatusArea(this.uuid, this._button);
        this._button.menu.connect('open-state-changed', (_, open) => {
            if (open && this._data) this._renderMenu();
        });
        this._refresh(false);
        this._timer = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 60, () => {
            if (this._data) this._render();
            this._refresh(false);
            return GLib.SOURCE_CONTINUE;
        });
    }
    _line(text, dim = false) {
        const item = new PopupMenu.PopupMenuItem(text, {reactive: false});
        if (dim) item.label.style = 'color: #9ea9b8; font-size: 11px;';
        this._button.menu.addMenuItem(item);
    }
    _render() {
        const q = this._data.quota ?? {}, a = this._data.api ?? {};
        const bucket = q.buckets?.[0];
        const primary = bucket?.windows.find(w => w.kind === 'primary') ?? bucket?.windows[0];
        const secondary = bucket?.windows.find(w => w !== primary);
        const s = windowState(primary, q);
        const name = !bucket || bucket.id === 'codex' ? 'Codex' : bucket.name;
        this._quotaLabel.text = `${name} ${s.text}${s.stale ? ' ⚠' : ''}`;
        this._quotaLabel.style = `color: ${s.color};`;
        paint(this._bar, s);
        this._weekly.text = secondary ? `${duration(secondary.minutes)} ${windowState(secondary, q).text}` : '';
        this._weekly.visible = !!secondary;
        this._apiLabel.text = `API ${a.display_period === 'since_reset' ? '↺ ' : ''}${apiText(a)}`;
        this._apiLabel.style = '';
        this._button.accessible_name = `${this._quotaLabel.text} 남음, ${this._weekly.text}, ${this._apiLabel.text} 사용 금액`;
        this._renderMenu();
    }
    _renderMenu() {
        const q = this._data.quota ?? {}, a = this._data.api ?? {};
        this._button.menu.removeAll();
        this._line('CODEX · 남은 사용 한도');
        for (const bucket of q.buckets ?? []) {
            if (bucket.id !== 'codex') this._line(bucket.name);
            for (const w of bucket.windows) {
                const s = windowState(w, q);
                this._line(`${duration(w.minutes)} 한도     ${s.text}${s.known ? ' 남음' : ''}${s.stale ? ' · 이전 값' : ''}`);
                const item = new PopupMenu.PopupBaseMenuItem({reactive: false});
                const bar = meter(290, 9);
                paint(bar, s);
                item.add_child(bar.track);
                this._button.menu.addMenuItem(item);
                this._line(resetText(w), true);
                this._line(`리셋 ${new Date(w.resets_at*1000).toLocaleString()}`, true);
            }
        }
        if (!q.buckets?.length) this._line('한도 확인 필요 · Codex 로그인과 설치 경로 확인');
        if (q.status === 'error') this._line(`조회 실패: ${q.error}`, true);
        if (q.updated) this._line(`마지막 확인 ${new Date(q.updated*1000).toLocaleString()}`, true);
        this._button.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        this._line('OPENAI API · 사용 금액');
        this._line(`${a.display_period === 'since_reset' ? '초기화 이후' : '이번 달'}  ${apiText(a)}`);
        if (a.month_usd !== undefined) {
            this._line(`오늘 $${a.today_usd.toFixed(4)} · 이번 달 $${a.month_usd.toFixed(4)}`, true);
            if (a.reset_at) this._line(`표시 초기화 ${new Date(a.reset_at*1000).toLocaleString()}`, true);
            this._line(`마지막 확인 ${new Date(a.updated*1000).toLocaleString()}`, true);
            for (const [name, v] of Object.entries(a.models ?? {}).slice(0, 8))
                this._line(`${name}: 입력 ${v.input.toLocaleString()} / 출력 ${v.output.toLocaleString()}`, true);
        }
        if (a.status === 'unconfigured') this._line('Admin API key 연결 필요', true);
        if (a.status === 'error') this._line(`갱신 실패: ${a.error} · 이전 값`, true);
        this._line('조직 전체 · UTC 기준 · 서버 집계 지연 가능', true);
        this._button.menu.addAction('API 표시 사용량 초기화', () => this._action('--reset-api'));
        if (a.display_period === 'since_reset')
            this._button.menu.addAction('이번 달 사용 금액으로 돌아가기', () => this._action('--monthly-api'));
        this._button.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        this._button.menu.addAction('새로고침', () => this._refresh(true));
        this._button.menu.addAction('API 사용량 대시보드', () => this._open('https://platform.openai.com/usage'));
        this._button.menu.addAction('설정 방법 열기', () => this._open(Gio.File.new_for_path(`${this.path}/README.md`).get_uri()));
    }
    _open(uri) {
        try { Gio.AppInfo.launch_default_for_uri(uri, null); }
        catch (_) { Main.notify('AI Usage', '기본 앱으로 열지 못했습니다. README를 확인하세요.'); }
    }
    _action(flag) {
        if (this._actionProc) return;
        try {
            const proc = Gio.Subprocess.new(['python3', `${this.path}/collector.py`, flag],
                Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_SILENCE);
            this._actionProc = proc;
            proc.communicate_utf8_async(null, null, (p, res) => {
                if (this._actionProc !== p) return;
                this._actionProc = null;
                if (!this._button) return;
                try {
                    const [, output] = p.communicate_utf8_finish(res);
                    const result = JSON.parse(output);
                    if (!p.get_successful() || !result.ok) throw new Error();
                    Main.notify('AI Usage', flag === '--reset-api' ? '표시 금액을 초기화했습니다. 실제 과금 기록은 유지됩니다.' : '이번 달 사용 금액으로 돌아갑니다.');
                    this._refreshPending = true;
                    if (!this._proc) { this._refreshPending = false; this._refresh(true); }
                } catch (_) { Main.notify('AI Usage', '초기화 실패 · 기존 표시 기준을 유지합니다.'); }
            });
        } catch (_) { Main.notify('AI Usage', '초기화 명령을 실행하지 못했습니다.'); }
    }
    _refresh(force) {
        if (this._proc || !this._button) return;
        try {
            const args = ['python3', `${this.path}/collector.py`];
            if (force) args.push('--refresh');
            const proc = Gio.Subprocess.new(args, Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_SILENCE);
            this._proc = proc;
            this._deadline = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 90, () => {
                this._deadline = null;
                proc.force_exit();
                return GLib.SOURCE_REMOVE;
            });
            proc.communicate_utf8_async(null, null, (p, res) => {
                if (this._proc !== p) return;
                this._proc = null;
                if (this._deadline) GLib.Source.remove(this._deadline);
                this._deadline = null;
                if (!this._button) return;
                try {
                    const [, stdout] = p.communicate_utf8_finish(res);
                    if (!p.get_successful()) throw new Error('collector failed');
                    this._data = JSON.parse(stdout);
                    this._render();
                } catch (_) { this._failed(); }
                if (this._refreshPending) { this._refreshPending = false; this._refresh(true); }
            });
        } catch (_) { this._failed(); }
    }
    _failed() {
        if (this._data) {
            for (const part of ['quota', 'api']) {
                this._data[part].status = 'error';
                this._data[part].error = '수집기 오류 · 재시도 중';
            }
            this._render();
        } else {
            this._quotaLabel.text = 'Codex 확인 필요';
            this._apiLabel.text = 'API 확인 필요';
        }
    }
    disable() {
        if (this._timer) GLib.Source.remove(this._timer);
        if (this._deadline) GLib.Source.remove(this._deadline);
        this._timer = this._deadline = null;
        this._actionProc?.force_exit();
        this._actionProc = null;
        this._refreshPending = false;
        this._proc?.force_exit();
        this._proc = null;
        this._button?.destroy();
        this._button = this._data = this._quotaLabel = this._apiLabel = this._bar = this._weekly = null;
    }
}
