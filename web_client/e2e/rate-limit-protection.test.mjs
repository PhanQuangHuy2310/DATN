import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
const source = readFileSync(new URL('../src/api.js', import.meta.url), 'utf8')
  .replace('import.meta.env.VITE_API_BASE_URL', 'undefined');
let moduleIndex = 0;
const loadApi = () => import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}#${moduleIndex++}`);
const respond = (status, body, headers = {}) => new Response(JSON.stringify(body), {
  status, headers: { 'content-type': 'application/json', ...headers },
});

test('global 429 respects Retry-After without another network request; health stays callable', async () => {
  const priorFetch = globalThis.fetch;
  const priorDoc = globalThis.document;
  globalThis.document = { cookie: '' };
  let calls = 0;
  try {
    const { api } = await loadApi();
    globalThis.fetch = async (url) => {
      calls++;
      if (url === '/health/live') return respond(200, { status: 'ok' });
      return respond(429, { error: { code: 'RATE_LIMIT_EXCEEDED' } }, { 'Retry-After': '60' });
    };
    await assert.rejects(api('/api/v1/auth/csrf'), e => e.status === 429 && e.retryAfterMs >= 59000);
    assert.equal(calls, 1);
    await assert.rejects(api('/api/v1/system/ai-status'), e => e.status === 429 && e.retryAfterMs > 0);
    await assert.rejects(api('/api/v1/auth/login', { method: 'POST', body: '{}' }), e => e.status === 429);
    assert.equal(calls, 1, 'requests during 429 cooldown must not hit Django');
    assert.deepEqual(await api('/health/live'), { status: 'ok' });
    assert.equal(calls, 2, 'health probe is not rate-limited by middleware');
  } finally {
    globalThis.fetch = priorFetch;
    globalThis.document = priorDoc;
  }
});

test('CSRF initialization shares one request and skips fetching for existing cookie', async () => {
  const priorFetch = globalThis.fetch;
  const priorDoc = globalThis.document;
  globalThis.document = { cookie: '' };
  let calls = 0;
  try {
    const { initializeCsrf } = await loadApi();
    globalThis.fetch = async () => {
      calls++;
      await new Promise(resolve => setTimeout(resolve, 10));
      globalThis.document.cookie = 'csrftoken=known-token';
      return respond(200, { status: 'ok' });
    };
    await Promise.all([initializeCsrf(), initializeCsrf(), initializeCsrf()]);
    await initializeCsrf();
    assert.equal(calls, 1, 'same-tab calls should reuse the cookie/in-flight promise');
  } finally {
    globalThis.fetch = priorFetch;
    globalThis.document = priorDoc;
  }
});

test('AI status and regulations stop aggressive 1.5s / 2.5s polling', () => {
  const src = (path) => readFileSync(new URL(path, import.meta.url), 'utf8');
  const ai = src('../src/components/AiEngineManagementPage.jsx');
  const regs = src('../src/components/RegulationsManagementPage.jsx');
  const app = src('../src/App.jsx');
  assert.doesNotMatch(ai, /setInterval\(poll,\s*1500\)/);
  assert.doesNotMatch(regs, /setInterval\([^]*?\},\s*2500\)/);
  assert.match(ai, /error\?\.status === 429/);
  assert.match(app, /const delay = Math\.max\(60000, e\.retryAfterMs/);
});
