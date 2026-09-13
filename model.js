// Pure display logic, shared with tests. Expired windows never imply 100%.
export function duration(minutes) {
    if (!Number.isFinite(minutes) || minutes <= 0) return '현재 한도';
    if (minutes === 10080) return '주간';
    if (minutes % 1440 === 0) return `${minutes / 1440}일`;
    if (minutes % 60 === 0) return `${minutes / 60}시간`;
    return `${minutes}분`;
}
export function windowState(window, quota, now = Date.now()/1000) {
    if (!window || !Number.isFinite(window.remaining) || !Number.isFinite(window.resets_at))
        return {known: false, text: '확인 필요', color: '#87909d'};
    if (now >= window.resets_at)
        return {known: false, text: '리셋 확인 중', color: '#87909d'};
    const stale = quota.status !== 'ok' || !quota.updated || now-quota.updated > 300;
    const value = Math.max(0, Math.min(100, window.remaining));
    // Floor so a small positive allowance never rounds up to full allowance.
    return {known: true, value, stale, text: `${Math.floor(value)}%`,
        color: stale ? '#87909d' : value <= 10 ? '#ff7474' : value <= 30 ? '#f5bd62' : '#6ddbb6'};
}
export function resetText(window, now = Date.now()/1000) {
    if (!window || !Number.isFinite(window.resets_at)) return '리셋 시각 확인 필요';
    const mins = Math.ceil((window.resets_at-now)/60);
    if (mins <= 0) return '리셋 시각 경과 · 새 값 대기';
    const days = Math.floor(mins/1440), hours = Math.floor((mins%1440)/60), rest = mins%60;
    return `${days ? `${days}일 ` : ''}${hours ? `${hours}시간 ` : ''}${rest}분 후 리셋`;
}
export function apiText(api) {
    if (Number.isFinite(api.display_usd))
        return `$${api.display_usd.toFixed(2)}${api.status === 'error' ? ' ⚠' : ''}`;
    return api.status === 'unconfigured' ? '미연결' : '확인 필요';
}
