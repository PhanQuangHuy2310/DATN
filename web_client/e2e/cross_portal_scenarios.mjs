// Client Phase 1-3 acceptance: 5 cross-portal scenarios in a real browser.
// Run against a stack you may write to (local replica), never production:
//   EAS_ADMIN_PASSWORD=... node e2e/cross_portal_scenarios.mjs
// Writes screenshots + test-results/cross-portal/report.html.
import { chromium, request } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";

const CLIENT = process.env.EAS_CLIENT_URL || "http://localhost:5173";
const ADMIN = process.env.EAS_ADMIN_URL || "http://127.0.0.1:8081";
const API = process.env.EAS_API_URL || "http://127.0.0.1:8000";
const ADMIN_PASSWORD = process.env.EAS_ADMIN_PASSWORD || "Password@123456";
const PASSWORD = "Password@123456";
const EMPLOYEE = process.env.EAS_EMPLOYEE || "hung.nguyen@eas.com";
const OUT = "test-results/cross-portal";
mkdirSync(OUT, { recursive: true });
const steps = [];
let shotNo = 0;

const browser = await chromium.launch({ headless: !process.env.HEADED, slowMo: process.env.HEADED ? 250 : 0 });

async function shot(page, label) {
  const file = `${String(++shotNo).padStart(2, "0")}.png`;
  await page.screenshot({ path: `${OUT}/${file}` });
  return file;
}
function record(scenario, name, ok, detail, file) {
  steps.push({ scenario, name, ok: Boolean(ok), detail: String(detail ?? ""), file });
  console.log(`${ok ? "PASS" : "FAIL"} [${scenario}] ${name}${detail ? " — " + detail : ""}`);
}

// Admin API session (same rules as the admin UI; used to flip rights quickly).
const admin = await request.newContext({ baseURL: API, extraHTTPHeaders: { Origin: API, Referer: `${API}/` } });
await admin.get("/api/v1/auth/csrf");
const csrf = async () => (await admin.storageState()).cookies.find((c) => c.name === "csrftoken")?.value;
const call = async (method, path, data) =>
  admin.fetch(path, { method, data, headers: { "X-CSRFToken": await csrf(), "Content-Type": "application/json" } });
await call("POST", "/api/v1/auth/login", { email: "admin@eas.com", password: ADMIN_PASSWORD, portal: "admin" });

async function openPortal(url, email, password) {
  const context = await browser.newContext({ viewport: { width: 1366, height: 860 } });
  const page = await context.newPage();
  await page.goto(url);
  await page.locator("#login-email, input[name=email]").first().fill(email);
  await page.locator('input[type="password"]').first().fill(password);
  await page.locator('button[type="submit"]').first().click();
  const nav = page.getByRole("navigation", { name: "Điều hướng chính" });
  const result = await Promise.race([
    nav.waitFor({ timeout: 25000 }).then(() => "in"),
    page.locator('.error, [role="alert"]').first().waitFor({ timeout: 25000 }).then(() => "blocked"),
  ]).catch(() => "timeout");
  return { context, page, result, nav };
}
async function dismissDialogs(page) {
  await page.waitForTimeout(1500);
  while (await page.locator("dialog[open]").count()) {
    await page.locator("dialog[open]").getByRole("button", { name: /Đã hiểu/ }).click().catch(() => {});
    await page.waitForTimeout(300);
  }
}
const navTexts = async (nav) => (await nav.locator(".nav-text").allInnerTexts()).map((t) => t.trim());

// ---- 1. admin@eas.com: admin portal yes, employee portal no ----------------
{
  const a = await openPortal(ADMIN, "admin@eas.com", ADMIN_PASSWORD);
  record("1", "admin@eas.com đăng nhập Cổng Quản trị", a.result === "in", a.result, await shot(a.page));
  await a.context.close();
  const c = await openPortal(CLIENT, "admin@eas.com", ADMIN_PASSWORD);
  const msg = c.result === "blocked" ? await c.page.locator('.error, [role="alert"]').first().innerText() : c.result;
  record("1", "admin@eas.com bị chặn ở Cổng Nhân viên", c.result === "blocked", msg, await shot(c.page));
  await c.context.close();
}

// ---- 2. employee: admin portal no, employee portal yes ---------------------
{
  const a = await openPortal(ADMIN, EMPLOYEE, PASSWORD);
  const msg = a.result === "blocked" ? await a.page.locator('.error, [role="alert"]').first().innerText() : a.result;
  record("2", `${EMPLOYEE} bị chặn ở Cổng Quản trị`, a.result === "blocked", msg, await shot(a.page));
  await a.context.close();
}
const emp = await openPortal(CLIENT, EMPLOYEE, PASSWORD);
await dismissDialogs(emp.page);
{
  const items = await navTexts(emp.nav);
  record("2", `${EMPLOYEE} vào Cổng Nhân viên`, emp.result === "in", items.join(" · "), await shot(emp.page));
  const forbidden = items.filter((t) => ["Phân quyền", "Quản trị AI", "Quản lý API", "Phiên bản hệ thống"].includes(t));
  record("2", "Không có 4 module hệ thống trên sidebar nhân viên", forbidden.length === 0, forbidden.join(", ") || "không có");
  const header = await emp.page.locator(".topbar").innerText();
  record("2", "Header: tên trang, tìm kiếm, trạng thái làm việc, sáng/tối, tài khoản", /Đang làm|Nghỉ làm|Công tác/.test(header), header.replace(/\s+/g, " ").slice(0, 160));
}

// ---- 3. admin grants "Người dùng" to the employee, step by step -------------
const me = await (await emp.page.request.get(`${CLIENT}/api/v1/auth/me`)).json();
const userId = me.user.id;
async function grant(field, value) {
  const r = await call("POST", "/api/v1/admin/rbac/user-permission", { user_id: userId, module_code: "users", permission_type: field, value });
  return r.status();
}
async function reloadEmployee() {
  await emp.page.reload();
  await emp.nav.waitFor({ timeout: 25000 });
  await dismissDialogs(emp.page);
}
async function openPeople() {
  await emp.nav.locator(".nav-item", { hasText: "Người dùng" }).click();
  await emp.page.getByRole("heading", { level: 1 }).filter({ hasText: /Người dùng/ }).waitFor({ timeout: 20000 });
  await emp.page.waitForTimeout(2500);
}
{
  await call("POST", `/api/v1/admin/rbac/user-permission/${userId}/reset`, {});
  await reloadEmployee();
  const before = await navTexts(emp.nav);
  record("3", "Chưa cấp quyền: không có mục Người dùng", !before.includes("Người dùng"), before.join(" · "), await shot(emp.page));

  record("3", "Admin cấp quyền Xem module Người dùng", (await grant("can_view", true)) === 200, "");
  await reloadEmployee();
  const after = await navTexts(emp.nav);
  record("3", "Sau khi cấp Xem: Người dùng hiện trên sidebar", after.includes("Người dùng"), after.join(" · "));
  await openPeople();
  const viewOnly = {
    add: await emp.page.getByRole("button", { name: /Thêm người dùng|Thêm nhân viên|Tạo người dùng/ }).count(),
    edit: await emp.page.locator('button[title*="Chỉnh sửa"], button:has-text("Sửa")').count(),
    lock: await emp.page.locator('button[title*="Khóa"], button:has-text("Khóa")').count(),
  };
  record("3", "Chỉ có Xem: không có nút Thêm/Sửa/Khoá", viewOnly.add + viewOnly.edit + viewOnly.lock === 0, JSON.stringify(viewOnly), await shot(emp.page));

  for (const [field, label, locator] of [
    ["can_create", "Thêm", () => emp.page.getByRole("button", { name: /Thêm người dùng|Thêm nhân viên|Tạo người dùng/ })],
    ["can_update", "Sửa", () => emp.page.locator('button[title*="Chỉnh sửa"], button:has-text("Sửa")')],
    ["can_delete", "Khoá", () => emp.page.locator('button[title*="Khóa"], button:has-text("Khóa")')],
  ]) {
    await grant(field, true);
    await reloadEmployee();
    await openPeople();
    const n = await locator().count();
    record("3", `Cấp thêm quyền ${label}: nút ${label} xuất hiện`, n > 0, `${n} nút`, await shot(emp.page));
  }
  await call("POST", `/api/v1/admin/rbac/user-permission/${userId}/reset`, {});
  await reloadEmployee();
  const reset = await navTexts(emp.nav);
  record("3", "Thu hồi về mặc định: Người dùng biến mất", !reset.includes("Người dùng"), reset.join(" · "));
}

// ---- 5. admin switches an integration off --------------------------------------
{
  const apis = await (await call("GET", "/api/v1/admin/mock-apis")).json();
  const hr = apis.apis.find((a) => a.api_code === "API_HR");
  await call("PATCH", `/api/v1/admin/mock-apis/${hr.id}/toggle`, {});
  await emp.page.waitForTimeout(5500); // integration cache TTL
  await emp.nav.locator(".nav-item", { hasText: "Yêu cầu & Quy trình" }).click();
  await emp.page.getByRole("heading", { level: 1, name: "Yêu cầu & Quy trình" }).waitFor({ timeout: 20000 });
  await emp.page.getByLabel("Tìm mẫu yêu cầu").fill("Nghỉ phép");
  const card = emp.page.locator(".request-catalog-card", { hasText: "Nghỉ phép" }).first();
  await card.waitFor({ timeout: 20000 });
  const warning = await card.locator(".request-catalog-warning").innerText().catch(() => "");
  const disabled = await card.getByRole("button", { name: "Tạo yêu cầu" }).isDisabled().catch(() => false);
  record("5", "Tắt API HR: mẫu Nghỉ phép báo không thể dùng, nút bị khoá", warning.includes("không thể sử dụng") && disabled, warning, await shot(emp.page));
  await call("PATCH", `/api/v1/admin/mock-apis/${hr.id}/toggle`, {});
  await emp.page.waitForTimeout(5500);
  await emp.page.getByRole("tab", { name: "Theo dõi 5 giai đoạn" }).click();
  await emp.page.getByRole("tab", { name: "Tạo yêu cầu mới" }).click();
  await emp.page.getByLabel("Tìm mẫu yêu cầu").fill("Nghỉ phép");
  const card2 = emp.page.locator(".request-catalog-card", { hasText: "Nghỉ phép" }).first();
  await card2.waitFor({ timeout: 20000 });
  const enabled = await card2
    .getByRole("button", { name: "Tạo yêu cầu" })
    .and(emp.page.locator(":enabled"))
    .waitFor({ timeout: 15000 })
    .then(() => true)
    .catch(() => false);
  record("5", "Bật lại API HR: mẫu Nghỉ phép dùng được", enabled, "", await shot(emp.page));
  await emp.page.getByRole("tab", { name: "Theo dõi 5 giai đoạn" }).click();
  await emp.page.waitForTimeout(2500);
  record("2", "Tab Theo dõi 5 giai đoạn", (await emp.page.locator(".stage-chip").count()) === 6, "", await shot(emp.page));
}

// ---- 4. admin edits a regulation: employee is moved out, then let back in ----
{
  const regs = await (await call("GET", "/api/v1/admin/regulations")).json();
  const reg = regs.regulations[0];
  await emp.page.nav?.waitFor?.();
  const res = await call("PATCH", `/api/v1/admin/regulations/${reg.id}`, { content: `${reg.content} (Rà soát ${Date.now()})`, change_summary: "Kiểm thử liên thông" });
  record("4", "Admin sửa quy định", res.status() === 200, (await res.json()).new_version);
  const overlay = await emp.page.locator(".client-maintenance-backdrop").waitFor({ timeout: 15000 }).then(() => true).catch(() => false);
  record("4", "Cổng Nhân viên hiện màn hình AI đang cập nhật", overlay, "", await shot(emp.page));
  const back = await emp.page.locator('input[type="password"]').first().waitFor({ timeout: 20000 }).then(() => true).catch(() => false);
  record("4", "Tự đăng xuất về màn hình đăng nhập", back, "", await shot(emp.page));
  await emp.page.waitForFunction(() => !document.querySelector('button[type="submit"]')?.disabled, null, { timeout: 300000, polling: 1000 });
  await emp.page.locator("#login-email, input[name=email]").first().fill(EMPLOYEE);
  await emp.page.locator('input[type="password"]').first().fill(PASSWORD);
  await emp.page.locator('button[type="submit"]').first().click();
  const again = await emp.nav.waitFor({ timeout: 25000 }).then(() => true).catch(() => false);
  await emp.page.waitForTimeout(2500);
  const dialog = await emp.page.locator("dialog[open]").getAttribute("aria-label").catch(() => null);
  record("4", "AI xong: đăng nhập lại được và thấy thông báo cập nhật", again, dialog || "", await shot(emp.page));
}

await emp.context.close();
await browser.close();
await admin.dispose();

const passed = steps.filter((s) => s.ok).length;
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
writeFileSync(
  `${OUT}/report.html`,
  `<!doctype html><html lang="vi"><meta charset="utf-8"><title>Kiểm thử liên thông 2 cổng</title>
<style>body{font:14px system-ui;margin:24px}td,th{border:1px solid #ddd;padding:6px;vertical-align:top}table{border-collapse:collapse;width:100%}
.ok{color:#047857;font-weight:700}.no{color:#b91c1c;font-weight:700}img{width:420px;border:1px solid #ccc}</style>
<h1>Kiểm thử liên thông Cổng Quản trị ↔ Cổng Nhân viên</h1><p>${new Date().toLocaleString("vi-VN")} · <b>${passed}/${steps.length}</b> bước đạt · tài khoản thử: ${esc(EMPLOYEE)}</p>
<table><tr><th>KB</th><th>Bước</th><th>Kết quả</th><th>Chi tiết</th><th>Ảnh</th></tr>
${steps.map((s) => `<tr><td>${s.scenario}</td><td>${esc(s.name)}</td><td class="${s.ok ? "ok" : "no"}">${s.ok ? "ĐẠT" : "KHÔNG ĐẠT"}</td><td>${esc(s.detail)}</td><td>${s.file ? `<a href="${s.file}" target="_blank"><img src="${s.file}"></a>` : ""}</td></tr>`).join("\n")}
</table></html>`,
);
console.log(`\nĐẠT ${passed}/${steps.length} — ${OUT}/report.html`);
