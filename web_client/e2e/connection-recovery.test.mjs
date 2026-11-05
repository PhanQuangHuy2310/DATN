import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const source = readFileSync(new URL('../src/api.js', import.meta.url), 'utf8')
  .replace('import.meta.env.VITE_API_BASE_URL', 'undefined');
const { api } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
const json = (status, value) => new Response(JSON.stringify(value), {
  status, headers: { 'content-type': 'application/json' },
});

test('many widgets cannot launch an unlimited number of concurrent GET requests', async () => {
  const original = globalThis.fetch;
  let active = 0;
  let maximum = 0;
  try {
    globalThis.fetch = async () => {
      active++;
      maximum = Math.max(maximum, active);
      await new Promise((resolve) => setTimeout(resolve, 4));
      active--;
      return json(200, { ok: true });
    };
    const results = await Promise.all(Array.from({ length: 22 }, (_, i) => api(`/api/v1/list-${i}`)));
    assert.equal(results.length, 22);
    assert.ok(maximum <= 5, `GET concurrency ${maximum} exceeded limit 5`);
    assert.ok(maximum > 1, 'safe reads should still run concurrently');
  } finally {
    globalThis.fetch = original;
  }
});

test('explicit user action can probe during circuit cooldown and recover', async () => {
  const original = globalThis.fetch;
  let calls = 0;
  let broken = true;
  try {
    globalThis.fetch = async () => {
      calls++;
      return broken
        ? json(503, { error: { code: 'DATABASE_TEMPORARILY_UNAVAILABLE' } })
        : json(200, { ok: true });
    };
    await assert.rejects(api('/api/v1/initial-failure'), (e) => e.status === 503);
    const afterFailure = calls;
    await assert.rejects(api('/api/v1/normal-cooldown'), (e) => e.message === 'BACKEND_TEMPORARILY_UNAVAILABLE');
    assert.equal(calls, afterFailure);
    broken = false;
    assert.deepEqual(await api('/api/v1/explicit-retry', { forceProbe: true }), { ok: true });
    assert.deepEqual(await api('/api/v1/after-recovery'), { ok: true });
  } finally {
    globalThis.fetch = original;
  }
});
