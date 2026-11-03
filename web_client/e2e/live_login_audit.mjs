// Logs every live account in through the real UI of both portals, takes a
// screenshot of what each one sees and writes test-results/live-login/report.html.
// Usage: EAS_ADMIN_PASSWORD=... node e2e/live_login_audit.mjs   (HEADED=1 to watch)
import { chromium } from "@playwright/test";
import { readFileSync, writeFileSync } from "node:fs";

const CLIENT = process.env.EAS_CLIENT_URL || "http://localhost:5173";
const ADMIN = process.env.EAS_ADMIN_URL || "http://127.0.0.1:8081";
const EMPLOYEE_PASSWORD = process.env.EAS_EMPLOYEE_PASSWORD || "Password@123456";
const ADMIN_PASSWORD = process.env.EAS_ADMIN_PASSWORD;
const OUT = process.env.EAS_OUT || "test-results/live-login";
const ADMIN_ONLY_LABELS = ["Người dùng", "Phân quyền", "Quản trị AI", "Quản lý API", "Phiên bản hệ thống", "Danh tính & phạm vi quyền", "Quy định"];
const accounts = JSON.parse(readFileSync("test-results/live-login/accounts.json", "utf8"));
const only = process.env.ONLY ? process.env.ONLY.split(",") : null;
const list = only ? accounts.filter((a) => only.includes(a.email)) : accounts;

const browser = await chromium.launch({ headless: !process.env.HEADED, slowMo: process.env.HEADED ? 350 : 0 });

async function login(url, email, password, shot) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const page = await context.newPage();
  const result = { ok: false, nav: [], error: "", shot };
  try {
    await page.goto(url);
    await page.locator("#login-email, input[name=email]").first().fill(email);
    await page.locator('input[type="password"]').first().fill(password);
    await page.locator('button[type="submit"]').first().click();
    const nav = page.getByRole("navigation", { name: "Điều hướng chính" });
    const err = page.locator('.error, [role="alert"], .auth-error, .form-error').first();
    const outcome = await Promise.race([
      nav.waitFor({ timeout: 25000 }).then(() => "nav"),
      err.waitFor({ timeout: 25000 }).then(() => "error"),
      page.getByRole("heading", { name: /Không có quyền quản trị|Tài khoản quản trị/ }).waitFor({ timeout: 25000 }).then(() => "denied"),
    ]).catch(() => "timeout");
    if (outcome === "nav") {
      result.ok = true;
      await page.waitForTimeout(1500);
      while (await page.locator("dialog[open]").count()) {
        await page.locator("dialog[open]").getByRole("button", { name: /Đã hiểu/ }).click().catch(() => {});
        await page.waitForTimeout(300);
      }
      result.nav = (await nav.locator(".nav-text").allInnerTexts()).map((t) => t.trim()).filter(Boolean);
      result.who = (await page.locator(".topbar-user-pill, .topbar-right").first().innerText().catch(() => "")).replace(/\s+/g, " ").trim();
    } else if (outcome === "error") {
      result.error = (await err.innerText()).trim();
    } else if (outcome === "denied") {
      result.error = (await page.locator("main").innerText()).replace(/\s+/g, " ").trim().slice(0, 200);
    } else {
      result.error = "Không phản hồi trong 25s";
    }
    await page.screenshot({ path: `${OUT}/${shot}`, type: "jpeg", quality: 55 });
  } catch (e) {
    result.error = `Lỗi script: ${e.message.slice(0, 120)}`;
  }
  await context.close();
  return result;
}

const results = [];
const queue = [...list];
async function worker() {
  while (queue.length) {
    const a = queue.shift();
    const isAdmin = a.email === "admin@eas.com";
    const password = isAdmin ? ADMIN_PASSWORD : EMPLOYEE_PASSWORD;
    const slug = a.email.replace(/[^a-z0-9]/gi, "_");
    const client = await login(CLIENT, a.email, password, `${slug}_client.jpg`);
    const admin = await login(ADMIN, a.email, password, `${slug}_admin.jpg`);
    const adminItems = client.nav.filter((l) => ADMIN_ONLY_LABELS.includes(l));
    const pass = isAdmin
      ? admin.ok && !client.ok && admin.nav.length === 9
      : client.ok && !admin.ok && adminItems.length === 0;
    results.push({ ...a, isAdmin, client, admin, adminItems, pass });
    console.log(`${pass ? "PASS" : "FAIL"} ${a.email.padEnd(32)} client:${client.ok ? "vào được" : "bị chặn"} admin:${admin.ok ? "vào được" : "bị chặn"}${adminItems.length ? " ADMIN-MENU:" + adminItems.join("|") : ""}${!pass ? " | " + (client.error || admin.error) : ""}`);
  }
}
await Promise.all(Array.from({ length: process.env.HEADED ? 1 : 4 }, worker));
await browser.close();

results.sort((x, y) => (y.isAdmin - x.isAdmin) || x.dept.localeCompare(y.dept) || x.email.localeCompare(y.email));
const passed = results.filter((r) => r.pass).length;
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const cell = (r) => r.ok
  ? `<span class="ok">Vào được</span><div class="nav">${r.nav.map(esc).join(" · ")}</div>`
  : `<span class="no">Bị chặn</span><div class="msg">${esc(r.error)}</div>`;
const html = `<!doctype html><html lang="vi"><meta charset="utf-8"><title>Kiểm tra đăng nhập live</title>
<style>body{font:14px system-ui;margin:24px;color:#111}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ddd;padding:6px;vertical-align:top}
th{background:#f3f4f6;position:sticky;top:0}.ok{color:#047857;font-weight:600}.no{color:#b91c1c;font-weight:600}.nav,.msg{font-size:12px;color:#444;margin-top:4px}
img{width:240px;border:1px solid #ccc;cursor:zoom-in}.pass{background:#ecfdf5}.fail{background:#fef2f2}h1{margin:0 0 4px}</style>
<h1>Đăng nhập thật trên hệ thống live — ${new Date().toLocaleString("vi-VN")}</h1>
<p><b>${passed}/${results.length}</b> tài khoản đúng yêu cầu. Cổng nhân viên: ${CLIENT} · Cổng quản trị: ${ADMIN}.
Quy tắc: chỉ admin@eas.com vào được cổng quản trị (đủ 9 mục) và bị chặn ở cổng nhân viên; mọi tài khoản khác vào được cổng nhân viên, không thấy mục quản trị, bị chặn ở cổng quản trị.</p>
<table><tr><th>#</th><th>Tài khoản</th><th>Vai trò (DB)</th><th>Cổng nhân viên</th><th>Ảnh</th><th>Cổng quản trị</th><th>Ảnh</th><th>Kết quả</th></tr>
${results.map((r, i) => `<tr class="${r.pass ? "pass" : "fail"}"><td>${i + 1}</td><td><b>${esc(r.email)}</b><br>${esc(r.name)}<br><small>${esc(r.dept)}</small></td><td>${esc(r.roles)}</td>
<td>${cell(r.client)}</td><td><a href="${r.client.shot}" target="_blank"><img loading="lazy" src="${r.client.shot}"></a></td>
<td>${cell(r.admin)}</td><td><a href="${r.admin.shot}" target="_blank"><img loading="lazy" src="${r.admin.shot}"></a></td>
<td>${r.pass ? '<span class="ok">ĐẠT</span>' : '<span class="no">KHÔNG ĐẠT</span>'}</td></tr>`).join("\n")}
</table></html>`;
writeFileSync(`${OUT}/report.html`, html);
console.log(`\nĐẠT ${passed}/${results.length} — báo cáo: ${OUT}/report.html`);
