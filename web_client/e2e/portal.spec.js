import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const CLIENT = "http://127.0.0.1:4173";
const ADMIN = "http://127.0.0.1:4174";
const REQ = "11111111-1111-4111-8111-111111111111";
const ME = "22222222-2222-4222-8222-222222222222";
const STEP = "33333333-3333-4333-8333-333333333333";
const OTHER = "44444444-4444-4444-8444-444444444444";

const USERS = {
  requester: { roles: ["REQUESTER", "ACCEPTOR"], capabilities: {} },
  approver: { roles: ["APPROVER", "REQUESTER", "ACCEPTOR"], capabilities: {} },
  ops: { roles: ["OPS_ADMIN"], capabilities: { identity_manage: true } },
};

function listItem(overrides = {}) {
  return {
    id: REQ, code: "REQ-2026-0012", type_code: "LEAVE", type_name: "Nghỉ phép thường niên", status: "PENDING_APPROVAL",
    lock_version: 3, created_at: "2026-10-07T07:00:00Z", updated_at: "2026-10-07T07:00:00Z", risk_weight: 1, approval_level: 2,
    requester_name: "Trần Văn Bình", current_assignee_name: "Nguyễn Minh Anh", due_at: "2026-10-08T07:00:00Z", overdue: true,
    ...overrides,
  };
}

function detail(kind) {
  return {
    ...listItem(), requester_id: OTHER, revision_no: 1,
    payload: { title: "Nghỉ phép tháng 10", start_date: "2026-10-25", end_date: "2026-10-26", reason: "Việc gia đình" },
    approval_steps: [
      { step_no: 1, assignee_id: kind === "approver" ? ME : OTHER, assignee_name: "Nguyễn Minh Anh", state: "ACTIVE", activated_at: "2026-10-07T07:00:00Z", closed_at: null, tier_level: 1, resolver_code: "DIRECT_MANAGER" },
      { step_no: 2, assignee_id: OTHER, assignee_name: "Bùi Thị Hà", state: "WAITING", activated_at: null, closed_at: null, tier_level: 2, resolver_code: "HR_MANAGER" },
    ],
    workflow: { lifecycle: "A", planned_executor_id: null, acceptor_id: null, attempt: null },
    progress: {
      stage: "APPROVAL", requester_name: "Trần Văn Bình", type_name: "Nghỉ phép thường niên", department_name: "Phòng Kế toán",
      current_assignee: { id: ME, name: "Nguyễn Minh Anh", role: "APPROVER", resolver_code: "DIRECT_MANAGER" },
      next_assignee: { id: OTHER, name: "Bùi Thị Hà", role: "APPROVER", resolver_code: "HR_MANAGER" },
      executor: null, acceptor: null,
      deadline: { kind: "APPROVAL", started_at: "2026-10-07T07:00:00Z", due_at: "2026-10-08T07:00:00Z", remaining_seconds: -86400, overdue: true },
      decisions: [{ kind: "APPROVAL", revision_no: 1, step_no: 1, outcome: "NEEDS_INFO", reason: "Bổ sung ngày bắt đầu nghỉ", decided_at: "2026-10-06T07:00:00Z", actor_name: "Nguyễn Minh Anh" }],
    },
  };
}

async function mock(page, kind) {
  const calls = [];
  const user = { id: ME, display_name: "Nguyễn Minh Anh", department_id: "d1", ...USERS[kind] };
  await page.route(/\/(api\/v1|health)\//, async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const path = url.pathname.replace(/^\/api\/v1\//, "");
    let body = req.postData();
    try { body = JSON.parse(body); } catch { /* not JSON */ }
    calls.push({ path, method: req.method(), body, url });
    const send = (value, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(value) });
    if (url.pathname === "/health/ready") return send({ status: "ready", checks: { database: true, shared_security_cache: true } });
    if (path === "auth/csrf") return send({});
    if (path === "auth/me") return send({ user });
    if (path === "notifications") return send({ items: [{ id: "n1", label: "Bạn có một yêu cầu cần phê duyệt", request_id: REQ, created_at: "2026-10-07T07:00:00Z", read_at: null }], unread_count: 1, next_offset: null });
    if (path === "notifications/n1/read") return send({ notification: { id: "n1", read_at: "2026-10-07T08:00:00Z" } });
    if (path === "reports/requests") return send({ report: { submitted: 4, approved: 3, completed: 2, completed_rate: 0.5, approved_rate: 0.75, avg_completion_hours: 26, avg_approval_hours: 6, by_status: { PENDING_APPROVAL: 1, COMPLETED: 2, REJECTED: 1 }, top_types: [{ code: "LEAVE", name: "Nghỉ phép thường niên", count: 3 }] } });
    if (path === "reports/team") return send({ report: { totals: { total: 3, pending: 1, in_progress: 0, completed: 2, rejected: 0, cancelled: 0, overdue: 1, awaiting_me: 1 }, departments: [{ department_id: "d1", department_name: "Phòng Kế toán", employees: 2, total: 3, pending: 1, in_progress: 0, completed: 2, rejected: 0, cancelled: 0, overdue: 1, awaiting_me: 1 }], employees: [{ department_id: "d1", department_name: "Phòng Kế toán", requester_id: OTHER, requester_name: "Trần Văn Bình", total: 3, pending: 1, in_progress: 0, completed: 2, rejected: 0, cancelled: 0, overdue: 1, awaiting_me: 1, avg_completion_hours: 30, avg_approval_hours: 5 }] } });
    if (path === "requests" && req.method() === "GET") return send({ items: [listItem()], next_offset: null });
    if (path === `requests/${REQ}`) return send({ request: detail(kind) });
    if (path === `requests/${REQ}/ai-assessments`) return send({ items: [] });
    if (path === `requests/${REQ}/history`) return send({ decisions: [], attempts: [], draft_attachments: [] });
    if (path === `requests/${REQ}/revisions`) return send({ revisions: [] });
    if (path === `requests/${REQ}/audit`) return send({ items: [{ id: "a1", action: "REQUEST_SUBMITTED", actor_kind: "HUMAN", actor_id: OTHER, occurred_at: "2026-10-05T07:00:00Z", details: {} }] });
    if (path === `requests/${REQ}/approval-decisions`) return send({ request: { id: REQ, status: "REJECTED", lock_version: 4 } });
    if (path === "request-types") return send({ items: [{ code: "LEAVE", name: "Nghỉ phép thường niên" }] });
    if (path === "meta/org-chart") return send({ scope: "department", departments: [{ id: "d1", code: "FIN", name: "Phòng Kế toán", parent_id: null, member_count: 2 }], users: [{ id: ME, display_name: "Nguyễn Minh Anh", department_id: "d1", manager_id: null }, { id: OTHER, display_name: "Trần Văn Bình", department_id: "d1", manager_id: ME }] });
    if (path === "admin/overview") return send({ total: 37, overdue: 13, by_status: { COMPLETED: 13, PENDING_APPROVAL: 6, REJECTED: 2, CANCELLED: 1 }, top_types: [{ code: "LEAVE", name: "Nghỉ phép thường niên", count: 12 }], by_department: [{ department_id: "d1", department_name: "Phòng Kế toán", total: 10, completed: 4, pending: 3, overdue: 2 }], users: { active: 40, total: 42 } });
    if (path === "admin/diagnostics") return send({ outbox: { counts: { SENT: 43, DEAD: 1 }, oldest_pending_seconds: null, last_sent_at: "2026-10-26T15:53:08Z", dead_events: [{ id: "e1", event_type: "SLA_BREACH", attempts: 4, last_error_code: "SMTP_TIMEOUT", created_at: "2026-10-20T00:00:00Z", replay_count: 0, request_code: "REQ-2026-0012" }] }, worker: { backlog_ok: true }, sla: { open_stages: 13, overdue_stages: 13, alerts_24h: {} }, ai_service: { healthy: false } });
    if (path.startsWith("admin/departments")) return send({ items: [{ id: "d1", name: "Phòng Kế toán", code: "FIN", is_active: true }], next_offset: null });
    if (path.startsWith("admin/users")) return send({ items: [{ id: OTHER, display_name: "Trần Văn Bình", email: "binh@eas.com" }], next_offset: null });
    if (path === "ops/requests") return send({ items: [{ ...listItem(), department_name: "Phòng Kế toán", active_step: { id: STEP, step_no: 1, assignee_id: ME }, current_attempt: null, acceptor_id: null, planned_executor_id: null, responsible: { name: "Nguyễn Minh Anh", stage: "APPROVAL" }, sla: { due_at: "2026-10-08T07:00:00Z" } }], next_offset: null });
    if (path === `requests/${REQ}/reassign`) return send({ request: { id: REQ } });
    return send({ items: [], next_offset: null });
  });
  return calls;
}

async function expectNoHorizontalOverflow(page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
}
async function expectHeaderClearsHeading(page) {
  const header = await page.locator(".topbar").boundingBox();
  const heading = await page.locator("main h1").first().boundingBox();
  expect(heading.y).toBeGreaterThanOrEqual(header.y + header.height - 1);
}

for (const width of [1440, 1024, 768, 375]) {
  test(`client layout fits ${width}px without overflow`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await mock(page, "approver");
    await page.goto(CLIENT);
    await expect(page.getByRole("heading", { level: 1 })).toContainText("Xin chào");
    await expectNoHorizontalOverflow(page);
    await expectHeaderClearsHeading(page);
    await expect(page.getByRole("button", { name: /^Thông báo/ })).toBeVisible();
    if (width <= 800) {
      await page.getByRole("button", { name: "Mở điều hướng" }).click();
      await expect(page.locator(".sidebar.open")).toBeVisible();
      await page.getByRole("button", { name: "Đóng điều hướng" }).click();
      await expect(page.locator(".sidebar.open")).toHaveCount(0);
      await page.getByRole("button", { name: "Mở điều hướng" }).click();
      await page.keyboard.press("Escape");
      await expect(page.locator(".sidebar.open")).toHaveCount(0);
    }
    const search = page.getByRole("combobox", { name: /Tìm nhanh/ });
    await search.fill("REQ");
    await page.locator("#ds-global-search-results").getByRole("button", { name: /REQ-2026-0012/ }).click();
    await expect(search).toHaveValue("");
    await expect(page.getByRole("tab", { name: "Người phê duyệt" })).toBeVisible();
    await expectNoHorizontalOverflow(page);
  });

  test(`admin layout fits ${width}px without overflow`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await mock(page, "ops");
    await page.goto(ADMIN);
    await expect(page.getByRole("heading", { name: "Tổng quan vận hành" })).toBeVisible();
    await expect(page.getByText("Tổng yêu cầu phát sinh")).toBeVisible();
    await expectNoHorizontalOverflow(page);
    await expectHeaderClearsHeading(page);
  });
}

test("client navigation follows the workspace groups and hides admin modules", async ({ page }) => {
  await mock(page, "requester");
  await page.goto(CLIENT);
  const nav = page.getByRole("navigation", { name: "Điều hướng chính" });
  for (const label of ["Tổng quan", "Yêu cầu của tôi", "Sơ đồ tổ chức", "Sơ đồ luồng", "Quy trình AI", "Tài khoản cá nhân"]) {
    await expect(nav.getByRole("button", { name: label, exact: true })).toBeVisible();
  }
  for (const label of ["Theo dõi vận hành", "Quản lý người dùng", "Tổng quan phòng ban", "Chờ phê duyệt"]) {
    await expect(nav.getByRole("button", { name: label, exact: true })).toHaveCount(0);
  }
});

test("approver sees department management and drills into an employee", async ({ page }) => {
  await mock(page, "approver");
  await page.goto(CLIENT);
  await page.getByRole("navigation", { name: "Điều hướng chính" }).getByRole("button", { name: "Tổng quan phòng ban" }).click();
  await page.getByRole("button", { name: "Xem nhân viên →" }).click();
  await page.getByRole("button", { name: "Xem hồ sơ →" }).click();
  await expect(page.getByRole("heading", { name: "Hồ sơ của Trần Văn Bình" })).toBeVisible();
});

test("request detail shows progress, all tabs and requires a reason to reject", async ({ page }) => {
  const calls = await mock(page, "approver");
  await page.goto(CLIENT);
  await page.getByRole("button", { name: /Thông báo, 1 chưa đọc/ }).click();
  await page.getByRole("button", { name: /Bạn có một yêu cầu cần phê duyệt/ }).click();
  await expect.poll(() => calls.some((c) => c.path === "notifications/n1/read" && c.method === "POST")).toBe(true);
  await expect(page.getByLabel("Tình trạng xử lý hiện tại")).toContainText("Bùi Thị Hà");
  await expect(page.getByLabel("Tình trạng xử lý hiện tại")).toContainText("Quá hạn");
  for (const tab of ["Thông tin", "Tiến trình xử lý", "Người phê duyệt", "Tệp đính kèm", "Đánh giá AI", "Lịch sử hoạt động", "Sơ đồ luồng"]) {
    await page.getByRole("tab", { name: new RegExp(`^${tab}`) }).click();
    await expect(page.getByRole("tab", { name: new RegExp(`^${tab}`) })).toHaveAttribute("aria-selected", "true");
  }
  await page.getByRole("tab", { name: "Lịch sử hoạt động" }).click();
  await expect(page.getByText("Gửi yêu cầu").first()).toBeVisible();
  await page.getByRole("button", { name: "Từ chối", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("button", { name: "Xác nhận" }).click();
  expect(calls.some((c) => c.path.endsWith("approval-decisions"))).toBe(false);
  await dialog.getByLabel("Lý do / nhận xét").fill("Không đủ ngày phép còn lại");
  await dialog.getByRole("button", { name: "Xác nhận" }).click();
  await expect.poll(() => calls.find((c) => c.path.endsWith("approval-decisions"))?.body).toMatchObject({ outcome: "REJECT", reason: "Không đủ ngày phép còn lại", expected_version: 3 });
});

test("admin operations reassigns through a people picker with the step and version", async ({ page }) => {
  const calls = await mock(page, "ops");
  await page.goto(ADMIN);
  await page.getByRole("navigation", { name: "Điều hướng chính" }).getByRole("button", { name: "Theo dõi vận hành" }).click();
  for (const header of ["Người tạo", "Người đang xử lý", "Phòng ban", "Giai đoạn", "Hạn xử lý", "Quá hạn"]) {
    await expect(page.getByRole("columnheader", { name: header })).toBeVisible();
  }
  // Nine columns must fit a 1280px laptop without scrolling inside the table.
  const inner = await page.locator("#ops-results .table-wrap").evaluate((el) => el.scrollWidth - el.clientWidth);
  expect(inner).toBeLessThanOrEqual(1);
  await page.getByRole("button", { name: "Điều chuyển" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Người nhận mới").selectOption(OTHER);
  await dialog.getByLabel("Lý do / nhận xét").fill("Người duyệt nghỉ phép dài ngày");
  await dialog.getByRole("button", { name: "Xác nhận điều chuyển" }).click();
  await expect.poll(() => calls.find((c) => c.path.endsWith("/reassign"))?.body).toMatchObject({ target_kind: "APPROVAL_STEP", target_id: STEP, new_user_id: OTHER, expected_version: 3 });
});

test("admin navigation exposes system modules and no request creation", async ({ page }) => {
  await mock(page, "ops");
  await page.goto(ADMIN);
  const nav = page.getByRole("navigation", { name: "Điều hướng chính" });
  for (const label of ["Tổng quan", "Theo dõi vận hành", "Người dùng", "Sơ đồ công ty", "Yêu cầu & Quy trình", "Phân quyền", "Thông báo SLA", "Quản trị AI", "Phiên bản hệ thống"]) {
    await expect(nav.getByRole("button", { name: label, exact: true })).toBeVisible();
  }
  await expect(page.getByRole("button", { name: /Tạo yêu cầu mới/ })).toHaveCount(0);
  await nav.getByRole("button", { name: "Thông báo SLA" }).click();
  await expect(page.getByRole("cell", { name: "Quá hạn xử lý" })).toBeVisible();
  await page.getByRole("button", { name: "Thu gọn thanh điều hướng" }).click();
  await expect(page.locator(".app-shell.sidebar-collapsed")).toBeVisible();
});

for (const [name, url, kind] of [["client", CLIENT, "approver"], ["admin", ADMIN, "ops"]]) {
  test(`${name} home has no critical accessibility violations`, async ({ page }) => {
    await mock(page, kind);
    await page.goto(url);
    await expect(page.locator("main h1").first()).toBeVisible();
    const result = await new AxeBuilder({ page }).analyze();
    const critical = result.violations.filter((v) => v.impact === "critical");
    expect(critical.map((v) => `${v.id}: ${v.nodes.length}`)).toEqual([]);
  });
}
