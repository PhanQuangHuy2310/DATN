import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const read = (file) => readFileSync(new URL(file, import.meta.url), 'utf8');
const source = read('../src/api.js').replace('import.meta.env.VITE_API_BASE_URL', 'undefined');
const { api, getResource, invalidateResources } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
const respond = (body) => new Response(JSON.stringify(body), { status: 200, headers: {'content-type': 'application/json'} });

test('initial App does not statically load heavy feature screen modules', () => {
  const app = read('../src/App.jsx');
  for (const screen of ['RoleTasks','ClientRequests','NotificationsPage','ProfilePage','ClientRequestsHub','TeamDashboard']) {
    assert.match(app, new RegExp(`lazy\\(\\(\\) => import\\("\\./components/${screen}\\.jsx"\\)\\)`));
    assert.doesNotMatch(app, new RegExp(`^import .* from "\\./components/${screen}\\.jsx"`, 'm'));
  }
  assert.doesNotMatch(read('../src/components/AppHeader.jsx'), /from "\.\/NotificationsPage\.jsx"/);
  assert.match(read('../src/components/ClientRequestsHub.jsx'), /lazy\(\(\) => import\("\.\/WorkflowDiagrams\.jsx"\)\)/);
});

test('department options never call the employee organization API', () => {
  const requests = read('../src/components/ClientRequests.jsx');
  assert.match(requests, /useResource\("\/api\/v1\/meta\/departments"\)/);
  assert.doesNotMatch(requests, /useResource\("\/api\/v1\/meta\/org-chart"\)/);
});

test('resource caching keeps stable dropdowns warm and invalidates after changes', async () => {
  const oldFetch = globalThis.fetch;
  const oldWindow = globalThis.window;
  const oldDocument = globalThis.document;
  const now = Date.now;
  let timestamp = 1_000_000;
  let calls = 0;
  try {
    Date.now = () => timestamp;
    globalThis.document = { cookie: '' };
    globalThis.window = { dispatchEvent() {} };
    globalThis.fetch = async () => respond({ version: ++calls });
    invalidateResources();
    const departmentPath = '/api/v1/meta/departments';
    const changingPath = '/api/v1/notifications?limit=6';
    assert.equal((await getResource(departmentPath)).version, 1);
    assert.equal((await getResource(changingPath)).version, 2);
    timestamp += 45_000;
    assert.equal((await getResource(departmentPath)).version, 1, 'static picker cache should survive >20s');
    assert.equal((await getResource(changingPath)).version, 3, 'notifications should refresh after 20s');
    await api('/api/v1/request-drafts', { method: 'POST', body: '{}' });
    assert.equal((await getResource(departmentPath)).version, 5, 'mutation must invalidate picker cache');
  } finally {
    Date.now = now;
    globalThis.fetch = oldFetch;
    globalThis.window = oldWindow;
    globalThis.document = oldDocument;
  }
});

test('cached results are bounded despite many different search filter URLs', async () => {
  const oldFetch = globalThis.fetch;
  const oldWindow = globalThis.window;
  let calls = 0;
  try {
    globalThis.window = { dispatchEvent() {} };
    globalThis.fetch = async () => respond({ count: ++calls });
    invalidateResources();
    await getResource('/api/v1/meta/departments');
    for (let i = 0; i < 145; i++) {
      await getResource(`/api/v1/requests?tab=mine&q=${i}`);
    }
    assert.equal((await getResource('/api/v1/meta/departments')).count, 147,
      'the oldest static picker should be evicted once 120 distinct keys are held');
  } finally {
    globalThis.fetch = oldFetch;
    globalThis.window = oldWindow;
  }
});
