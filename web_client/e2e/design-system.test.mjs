import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { canNavigate } from "../src/rolePolicy.js";

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8");
const app = read("../src/App.jsx");

test("both portals load the shared design system last", () => {
  for (const main of ["../src/main.jsx", "../../web_admin/src/main.jsx"]) {
    const source = read(main);
    const imports = [...source.matchAll(/import "([^"]+\.css)"/g)].map((m) => m[1]);
    assert.ok(imports.at(-1).endsWith("design-system.css"), main);
  }
  assert.match(read("../src/design-system.css"), /--ds-primary:/);
});

test("client and admin keep separate navigation configurations", () => {
  assert.match(app, /const CLIENT_NAV = \[\s*\["Không gian cá nhân", \["home", "mine"\]\],\s*\["Công việc được giao", \["approval", "execution", "acceptance"\]\],\s*\["Quản lý phòng ban", \["team", "team-employees"\]\],\s*\["Tổ chức & công cụ", \["org-client", "flow-diagrams", "ai-process"\]\],\s*\["Tài khoản", \["profile"\]\],/);
  assert.match(app, /const ADMIN_NAV = \[/);
  for (const key of ["ops", "users", "departments", "permissions", "request-catalog", "policy", "sla", "ai-process", "audit", "system"]) {
    assert.match(app.slice(app.indexOf("const ADMIN_NAV")), new RegExp(`"${key}"`), key);
  }
  // Business request creation never appears in the admin portal.
  assert.match(app, /portal !== "admin" && \(user\?\.permissions\?\.by_module\?\.requests_workflows \? Boolean\(user\.permissions\.by_module\.requests_workflows\.can_create\) : user\.roles\.includes\("REQUESTER"\)\)/);
});

test("department pages and diagnostics are role and scope gated", () => {
  assert.ok(canNavigate(["APPROVER"], "team-employees"));
  assert.equal(canNavigate(["REQUESTER"], "team-employees"), false);
  assert.ok(canNavigate(["OPS_ADMIN"], "sla", { identity_manage: true }));
  assert.equal(canNavigate(["OPS_ADMIN"], "sla", {}), false);
  assert.equal(canNavigate(["OPS_ADMIN"], "departments", {}), false);
  assert.equal(canNavigate(["AUDITOR"], "system"), false);
});

test("operators pick people and events from lists, never by typing identifiers", () => {
  const pages = read("../src/components/AdminPages.jsx");
  assert.ok(!pages.includes('pattern="[0-9a-fA-F-]{36}"'));
  assert.match(pages, /\/api\/v1\/admin\/users\?limit=50&active=true&role=/);
  assert.match(pages, /dead_events/);
});

test("no full page reload is used for data synchronisation", () => {
  const dir = new URL("../src/components/", import.meta.url);
  // ErrorBoundary keeps an explicit, user-triggered reload to recover from a render crash.
  for (const file of readdirSync(dir).filter((f) => f.endsWith(".jsx") && f !== "ErrorBoundary.jsx")) {
    assert.ok(!read(`../src/components/${file}`).includes("location.reload"), file);
  }
  assert.ok(!app.includes("location.reload"));
});

test("request detail exposes the specified tabs and readable activity log", () => {
  const detail = read("../src/components/RequestDetail.jsx");
  for (const title of ["Thông tin", "Tiến trình xử lý", "Người phê duyệt", "Tệp đính kèm", "Đánh giá AI", "Lịch sử hoạt động", "Sơ đồ luồng"]) {
    assert.ok(detail.includes(`"${title}"`), title);
  }
  // The raw technical audit dump is gone.
  assert.ok(!detail.includes("<Data value={r.data?.items || r.data} technical />"));
  assert.match(detail, /<WorkflowTimeline items=\{timelineItems\(r\)\} \/>/);
});

test("submitting a request asks for confirmation first", () => {
  const editor = read("../src/components/RequestEditor.jsx");
  assert.match(editor, /if \(send\) \{ setConfirmSend\(true\); return; \}/);
  assert.match(editor, /<ConfirmDialog/);
});
