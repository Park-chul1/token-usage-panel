import test from 'node:test';
import assert from 'node:assert/strict';
import {duration, windowState, resetText, apiText} from './model.js';
const q = {status: 'ok', updated: 900};
test('remaining bar matches server percentage and thresholds', () => {
    for (const [remaining, color] of [[75,'#6ddbb6'],[30,'#f5bd62'],[10,'#ff7474'],[0,'#ff7474']]) {
        const state = windowState({remaining,resets_at:2000},q,1000);
        assert.equal(state.value,remaining); assert.equal(state.color,color);
    }
});
test('expired reset is unknown, not full quota', () => {
    assert.equal(windowState({remaining:75,resets_at:1000},q,1000).known,false);
    assert.equal(windowState(null,q,1000).known,false);
});
test('stale and failed snapshots are gray', () => {
    assert.equal(windowState({remaining:75,resets_at:2000},q,1300).color,'#87909d');
    assert.equal(windowState({remaining:75,resets_at:2000},{...q,status:'error'},1000).stale,true);
});
test('quota periods come from server, not a daily assumption', () => {
    assert.equal(duration(300),'5시간'); assert.equal(duration(10080),'주간');
    assert.equal(duration(null),'현재 한도');
    assert.equal(resetText({resets_at:4600},1000),'1시간 0분 후 리셋');
});
test('API cost supports zero and visibly marks stale values', () => {
    assert.equal(apiText({display_usd:0,status:'ok'}),'$0.00');
    assert.equal(apiText({display_usd:12.34,status:'error'}),'$12.34 ⚠');
    assert.equal(apiText({status:'unconfigured'}),'미연결');
});
