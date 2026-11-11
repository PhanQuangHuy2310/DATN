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

test('a failed API does not make subsequent GETs fail without trying the server', async () => {
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
    broken = false;
    // Formerly the second GET immediately raised BACKEND_TEMPORARILY_UNAVAILABLE
    // without making any request, forcing the user to refresh manually.
    assert.deepEqual(await api('/api/v1/after-idle-recovery'), { ok: true });
    assert.ok(calls > afterFailure);
    assert.deepEqual(await api('/api/v1/after-recovery'), { ok: true });
  } finally {
    globalThis.fetch = original;
  }
});

test('concurrent health and authentication requests bypass slow data GET queue', async () => {
  const original = globalThis.fetch;
  const releases = [];
  let pending = 0;
  let authCompleted = false;
  try {
    globalThis.fetch = (path) => {
      if (String(path).endsWith('/auth/me') || String(path).endsWith('/health/live')) {
        authCompleted = true;
        return Promise.resolve(json(200, { user: null }));
      }
      pending++;
      return new Promise((resolve) => { releases.push(() => resolve(json(200, { ok: true }))); });
    };
    const busy = Array.from({ length: 5 }, (_, i) => api(`/api/v1/busy-${i}`));
    await new Promise((resolve) => setTimeout(resolve, 15));
    assert.equal(pending, 5);
    await api('/api/v1/auth/me');
    assert.equal(authCompleted, true);
    releases.forEach((release) => release());
    await Promise.all(busy);
  } finally {
    globalThis.fetch = original;
  }
});

test('a timed-out read ends with an actionable error instead of hanging', async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = (_url, { signal }) => new Promise((_resolve, reject) => {
      signal.addEventListener('abort', () => {
        const error = new Error('aborted');
        error.name = 'AbortError';
        reject(error);
      }, { once: true });
    });
    await assert.rejects(api('/api/v1/read-timeout', { timeoutMs: 40 }),
      (error) => error.message === 'REQUEST_TIMED_OUT' && error.status === 0);
  } finally {
    globalThis.fetch = original;
  }
});

test('a failed mutation is not retried (avoids duplicate workflow actions)', async () => {
  const originalFetch = globalThis.fetch;
  const originalDocument = globalThis.document;
  let sent = 0;
  try {
    globalThis.document = { cookie: '' };
    globalThis.fetch = async () => {
      sent++;
      return json(503, { error: { code: 'DATABASE_TEMPORARILY_UNAVAILABLE' } });
    };
    await assert.rejects(
      api('/api/v1/requests/submit', { method: 'POST', body: '{}', silent: true }),
      (error) => error.status === 503,
    );
    assert.equal(sent, 1);
  } finally {
    globalThis.fetch = originalFetch;
    globalThis.document = originalDocument;
  }
});
