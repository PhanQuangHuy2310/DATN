import test from "node:test";
import assert from "node:assert/strict";
import { PERMISSIONS_CHANGED, createRefresher, notifyPermissionsChanged } from "../src/sessionRefresh.js";

function fakeClock() {
  let time = 0;
  const timers = [];
  return {
    now: () => time,
    schedule: (fn, wait) => { timers.push({ fn, at: time + wait }); return timers.length - 1; },
    cancel: (id) => { timers[id] = null; },
    advance(ms) {
      time += ms;
      for (const [i, t] of timers.entries()) if (t && t.at <= time) { timers[i] = null; t.fn(); }
    },
  };
}

test("first trigger refreshes immediately, bursts are merged", () => {
  const clock = fakeClock();
  let calls = 0;
  const r = createRefresher(() => { calls += 1; }, { minIntervalMs: 5000, ...clock });
  r.trigger();
  assert.equal(calls, 1);
  r.trigger(); r.trigger(); r.trigger();
  assert.equal(calls, 1);
  clock.advance(4999);
  assert.equal(calls, 1);
  clock.advance(1);
  assert.equal(calls, 2);
});

test("dispose cancels a pending refresh", () => {
  const clock = fakeClock();
  let calls = 0;
  const r = createRefresher(() => { calls += 1; }, { minIntervalMs: 1000, ...clock });
  r.trigger(); r.trigger();
  r.dispose();
  clock.advance(5000);
  assert.equal(calls, 1);
});

test("permission changes dispatch the refresh event", () => {
  const target = new EventTarget();
  let seen = 0;
  target.addEventListener(PERMISSIONS_CHANGED, () => { seen += 1; });
  notifyPermissionsChanged(target);
  assert.equal(seen, 1);
});
