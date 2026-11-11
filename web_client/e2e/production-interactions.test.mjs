import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const read = (p) => readFileSync(new URL(p, import.meta.url), 'utf8');
const originalApi = read('../src/api.js').replace('import.meta.env.VITE_API_BASE_URL', 'undefined');
let sequence = 0;
const loadApi = () => import(`data:text/javascript;base64,${Buffer.from(originalApi).toString('base64')}#${++sequence}`);
const respond = (status, body) => new Response(JSON.stringify(body), {
  status, headers: { 'Content-Type': 'application/json' },
});

// Prevent real network access; checks transport and cache state emitted to the UI.
test('one local success toast: toast:false still invalidates cached UI data', async () => {
  const old = [globalThis.fetch, globalThis.document, globalThis.window];
  const events = [];
  try {
    globalThis.document = { cookie: '' };
    globalThis.window = { dispatchEvent: (e) => events.push(e.type) };
    globalThis.fetch = async () => respond(200, { success: true, item: { id: 1 } });
    const { api } = await loadApi();
    await api('/api/v1/admin/users-management', { method: 'POST', body: '{}', toast: false });
    assert.ok(events.includes('eas:data-changed'));
    assert.equal(events.filter((event) => event === 'eas:toast').length, 0);
  } finally {
    [globalThis.fetch, globalThis.document, globalThis.window] = old;
  }
});

test('a 200 response with success:false is never reported as a completed mutation', async () => {
  const old = [globalThis.fetch, globalThis.document, globalThis.window];
  const events = [];
  try {
    globalThis.document = { cookie: '' };
    globalThis.window = { dispatchEvent: (e) => events.push(e.type) };
    globalThis.fetch = async () => respond(200, { success: false, message: 'Rejected by business rule' });
    const { api } = await loadApi();
    await assert.rejects(api('/api/v1/admin/request-templates', { method: 'PATCH', body: '{}' }), (error) => {
      assert.equal(error.message, 'OPERATION_NOT_CONFIRMED');
      assert.equal(error.serverMessage, 'Rejected by business rule');
      return true;
    });
    assert.equal(events.filter((event) => event === 'eas:data-changed').length, 0);
  } finally {
    [globalThis.fetch, globalThis.document, globalThis.window] = old;
  }
});

test('a failed mutation is not transparently retried (avoids accidental duplicate operations)', async () => {
  const old = [globalThis.fetch, globalThis.document, globalThis.window];
  let calls = 0;
  try {
    globalThis.document = { cookie: '' };
    globalThis.window = { dispatchEvent() {} };
    globalThis.fetch = async () => { calls++; return respond(503, { error: { code: 'SERVICE_UNAVAILABLE' } }); };
    const { api } = await loadApi();
    await assert.rejects(api('/api/v1/requests/submit', { method: 'POST', body: '{}' }), e => e.status === 503);
    assert.equal(calls, 1);
  } finally {
    [globalThis.fetch, globalThis.document, globalThis.window] = old;
  }
});

test('login/reset forms use native field validity and synchronous double-submit guard', () => {
  const app = read('../src/App.jsx');
  assert.match(app, /loginPendingRef\.current = true/);
  assert.match(app, /if \(loginPendingRef\.current\) return/);
  assert.match(app, /resetPendingRef\.current = true/);
  assert.match(app, /<form onSubmit=\{submit\}>/);
  assert.match(app, /<form onSubmit=\{submitReset\}>/);
  assert.doesNotMatch(app, /<form onSubmit=\{submit\} noValidate>/);
});

test('shared action forms block same-frame double submission and retain form on error', () => {
  const ui = read('../src/components/ui.jsx');
  assert.match(ui, /if \(submittingRef\.current\) return/);
  assert.match(ui, /submittingRef\.current = true/);
  assert.match(ui, /submittingRef\.current = false/);
  assert.match(ui, /catch \(err\) \{\s*setError\(errorText\(err\)\)/);
  assert.match(ui, /aria-busy=\{busy\}/);
});

test('confirmation dialogs close only after successfully awaited onConfirm', () => {
  const ui = read('../src/components/design.jsx');
  const part = ui.slice(ui.indexOf('export function ConfirmDialog('), ui.indexOf('/** Vertical timeline'));
  assert.match(part, /const result = await onConfirm\(values\)/);
  assert.match(part, /onClose\(\); \/\/ Only navigate\/close once/);
  assert.match(part, /if \(pendingRef\.current\) e\.preventDefault\(\)/);
  assert.match(part, /disabled=\{pending\}/);
});

test('request send confirmation does not disappear before server response', () => {
  const src = read('../src/components/RequestEditor.jsx');
  assert.match(src, /if \(persistPendingRef\.current\) throw/);
  assert.match(src, /if \(send\) throw err; \/\/ Keep confirmation visible/);
  assert.match(src, /await persist\(formElementRef\.current, true\)/);
  assert.doesNotMatch(src, /setConfirmSend\(false\);\s*await persist/);
  assert.match(src, /Tệp đính kèm chỉ nhận PDF\/JPG\/PNG và không quá 10 MB/);
});

test('approval and execution action retries reuse stable idempotency keys', () => {
  const src = read('../src/components/RequestDetail.jsx');
  assert.match(src, /const actionKeys = useRef\(new Map\(\)\)/);
  assert.match(src, /actionKey\("decision"\)/);
  assert.match(src, /actionKey\("submit"\)/);
  assert.match(src, /toast: false/);
  assert.match(src, /await done\(\)/);
});

test('admin user creation never pre-fills a reusable credential, and saving locks immediately', () => {
  const src = read('../src/components/UserManagementPage.jsx');
  assert.match(src, /password: "", \/\/ Never prefill/);
  assert.doesNotMatch(src, /User@123456/);
  assert.match(src, /if \(userPendingRef\.current\) return/);
  assert.match(src, /setEditUserModal\(null\);\s*setRefreshKey/);
});

test('template designer shows validation errors inline and does not close on failure', () => {
  const src = read('../src/components/RequestWorkflowsPage.jsx');
  assert.match(src, /if \(savingRef\.current\) return/);
  assert.match(src, /setFormError\("Nhập tên và mã mẫu/);
  assert.match(src, /formError && <p className="error" role="alert">/);
  assert.match(src, /return guardedMutation\("template-save"/);
  assert.match(src, /if \(res\.success\) \{\s*setEditingTemplate\(null\)/);
});

test('regulations and RBAC toggles cannot dispatch overlapping changes', () => {
  const regs = read('../src/components/RegulationsManagementPage.jsx');
  const rbac = read('../src/components/RolePermissionMatrixPage.jsx');
  assert.match(regs, /if \(submittingRef\.current\) return/);
  assert.match(regs, /submittingRef\.current = false/);
  assert.match(rbac, /pendingPermissionRef\.current\.has\(pendingId\)/);
  assert.match(rbac, /pendingPermissionRef\.current\.delete\(pendingId\)/);
});
