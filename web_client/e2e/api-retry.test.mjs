import assert from 'node:assert/strict';
import { test } from 'node:test';
import { api, retryDelayMs } from '../src/api.js';

function json(status, body, headers = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...headers },
  });
}

test('one GET retry handles transient database outage then succeeds', async () => {
  const oldFetch = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async () => ++calls === 1
    ? json(503, { error: { code: 'DATABASE_TEMPORARILY_UNAVAILABLE' } }, { 'Retry-After': '0' })
    : json(200, { items: [{ id: 'ok' }] });
  try {
    assert.deepEqual(await api('/api/v1/request-types'), { items: [{ id: 'ok' }] });
    assert.equal(calls, 2);
  } finally { globalThis.fetch = oldFetch; }
});

test('repeated outage: fail safely after at most one retry, preserve correlation', async () => {
  const oldFetch = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    return json(503, { error: { code: 'DATABASE_TEMPORARILY_UNAVAILABLE' }, correlation_id: 'test-reference' }, { 'Retry-After': '0' });
  };
  try {
    await assert.rejects(() => api('/api/v1/request-types'), (err) => err.status === 503 && err.correlationId === 'test-reference');
    assert.equal(calls, 2);
  } finally { globalThis.fetch = oldFetch; }
});

test('POST and PATCH are never automatically retried', async () => {
  const oldFetch = globalThis.fetch;
  const oldDocument = globalThis.document;
  globalThis.document = { cookie: '' };
  let calls = 0;
  globalThis.fetch = async () => { calls += 1; return json(503, { error: { code: 'DATABASE_TEMPORARILY_UNAVAILABLE' } }); };
  try {
    for (const method of ['POST', 'PATCH']) {
      await assert.rejects(() => api('/api/v1/requests', { method, body: '{}' }), (err) => err.status === 503);
    }
    assert.equal(calls, 2);
  } finally { globalThis.fetch = oldFetch; globalThis.document = oldDocument; }
});

test('401 is not retried', async () => {
  const oldFetch = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async () => { calls += 1; return json(401, { error: { code: 'UNAUTHORIZED' } }); };
  try {
    await assert.rejects(() => api('/api/v1/auth/me'), (err) => err.status === 401);
    assert.equal(calls, 1);
  } finally { globalThis.fetch = oldFetch; }
});

test('retry delay respects Retry-After with a cap', () => {
  assert.equal(retryDelayMs(json(503, {}, { 'Retry-After': '3' })), 3000);
  assert.equal(retryDelayMs(json(503, {}, { 'Retry-After': '10' })), 4000);
  assert.equal(retryDelayMs(json(503, {})), 500);
});

test('AbortSignal cancels the retry delay and prevents the second request', async () => {
  const oldFetch = globalThis.fetch;
  const controller = new AbortController();
  let calls = 0;
  globalThis.fetch = async () => { calls += 1; return json(503, {}, { 'Retry-After': '2' }); };
  try {
    const pending = api('/api/v1/request-types', { signal: controller.signal });
    await new Promise((resolve) => setTimeout(resolve, 10));
    controller.abort();
    await assert.rejects(() => pending, (err) => err.name === 'AbortError');
    assert.equal(calls, 1);
  } finally { globalThis.fetch = oldFetch; }
});
