import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

// Vite replaces import.meta.env at build time; substitute it in this Node-only
// test so we can exercise the actual API helper without a browser or dev server.
const source = readFileSync(new URL('../src/api.js', import.meta.url), 'utf8')
  .replace('import.meta.env.VITE_API_BASE_URL', 'undefined');
const { api, getResource } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);

const response = (status, data) => new Response(JSON.stringify(data), {
  status,
  headers: { 'content-type': 'application/json' },
});

test('503 readiness response retains database connectivity diagnostics', async () => {
  const original = globalThis.fetch;
  let calls = 0;
  try {
    globalThis.fetch = async () => {
      calls++;
      return response(503, { status: 'not_ready', checks: {
        database: true, shared_security_cache: false,
      }});
    };
    const health = await getResource('/health/ready');
    assert.equal(health.status, 'not_ready');
    assert.equal(health.checks.database, true);
    assert.equal(health.checks.shared_security_cache, false);
    assert.equal(calls, 1, 'readiness diagnostics should not be retried');
  } finally {
    globalThis.fetch = original;
  }
});

test('other failing API endpoints continue to reject', async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async () => response(503, { status: 'not_ready', checks: { database: false } });
    await assert.rejects(getResource('/api/v1/nonexistent-test-probe'), (err) => err.status === 503);
  } finally {
    globalThis.fetch = original;
  }
});


test('a confirmed shared database outage backs off other GETs, not diagnostic probes', async () => {
  const original = globalThis.fetch;
  const seen = [];
  try {
    globalThis.fetch = async (url) => {
      seen.push(url);
      if (url === '/health/db') return response(200, { status: 'ok', database: true });
      return response(503, { error: { code: 'DATABASE_TEMPORARILY_UNAVAILABLE' } });
    };
    // Probe resets a circuit opened by any previous test.
    await api('/health/db');
    await assert.rejects(api('/api/v1/test-db-outage'), (e) => e.status === 503);
    assert.equal(seen.length, 3, 'one health call and at most two backend reads');
    // The recovered transport uses a short shared backoff but DOES try again:
    // it must not hard-fail every new GET until a manual page reload.
    await assert.rejects(api('/api/v1/test-other-resource'), (e) =>
      e.status === 503 && e.message === 'DATABASE_TEMPORARILY_UNAVAILABLE');
    assert.equal(seen.length, 5, 'shared outage uses at most two attempts per read');
    await api('/health/db');
    assert.equal(seen.length, 6, 'diagnostics remain reachable during cooldown');
  } finally {
    globalThis.fetch = original;
  }
});

test('an endpoint-specific AI 503 does not trip the database outage circuit', async () => {
  const original = globalThis.fetch;
  let calls = 0;
  try {
    globalThis.fetch = async (url) => {
      calls++;
      if (url === '/health/db') return response(200, { database: true });
      if (url.includes('ai-service')) return response(503, { error: { code: 'AI_SERVICE_UNAVAILABLE' } });
      return response(200, { ok: true });
    };
    await api('/health/db');
    await assert.rejects(api('/api/v1/test-ai-service'), (e) => e.message === 'AI_SERVICE_UNAVAILABLE');
    assert.deepEqual(await api('/api/v1/test-other-working-service'), {ok:true});
    assert.equal(calls, 3, 'endpoint-specific AI 503 is not retried; other services remain available');
  } finally {
    globalThis.fetch = original;
  }
});
