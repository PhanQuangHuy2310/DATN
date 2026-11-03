// Live check of the AI-learning lock in the employee portal (local stack only).
// Run with ai_service stopped so the lock lasts through the retries.
import { chromium, request } from "@playwright/test";

const API = "http://127.0.0.1:8000";
const CLIENT = "http://localhost:5173";
const PASSWORD = "Password@123456";
const log = (...a) => console.log(new Date().toISOString().slice(11, 19), ...a);

const admin = await request.newContext({ baseURL: API, extraHTTPHeaders: { Origin: API, Referer: `${API}/` } });
await admin.get("/api/v1/auth/csrf");
const csrf = async () => (await admin.storageState()).cookies.find((c) => c.name === "csrftoken")?.value;
const post = async (method, path, data) =>
  admin.fetch(path, { method, data, headers: { "X-CSRFToken": await csrf(), "Content-Type": "application/json" } });
log("admin login", (await post("POST", "/api/v1/auth/login", { email: "admin@eas.com", password: PASSWORD })).status());

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 860 } });
await page.goto(CLIENT);
await page.getByLabel(/email/i).first().fill("trong.tran@eas.com");
await page.locator('input[type="password"]').first().fill(PASSWORD);
await page.locator('button[type="submit"]').first().click();
await page.getByRole("navigation", { name: "Điều hướng chính" }).waitFor();
log("employee signed in");

const regs = await (await admin.get("/api/v1/admin/regulations")).json();
const reg = regs.regulations.find((r) => r.code === "REG-001") || regs.regulations[0];
const res = await post("PATCH", `/api/v1/admin/regulations/${reg.id}`, { content: `${reg.content} (Rà soát ${Date.now()})`, change_summary: "Kiểm thử khoá bảo trì" });
log("admin edits regulation", res.status(), (await res.json()).new_version);

await page.locator(".client-maintenance-backdrop").waitFor({ timeout: 15000 });
log("overlay shown:", (await page.locator(".client-maintenance-title").innerText()).replace(/\s+/g, " "));
await page.screenshot({ path: "test-results/live-lock-overlay.png" });
await page.locator('input[type="password"]').first().waitFor({ timeout: 15000 });
log("auto signed out to login screen");
const submit = page.locator('button[type="submit"]').first();
log("login button while locked:", await submit.isDisabled() ? "disabled" : "enabled", "|", (await submit.innerText()).trim());
await page.screenshot({ path: "test-results/live-lock-login.png" });

const started = Date.now();
await submit.waitFor({ state: "attached" });
await page.waitForFunction(() => !document.querySelector('button[type="submit"]')?.disabled, null, { timeout: 300000, polling: 1000 });
log(`login re-enabled after ${Math.round((Date.now() - started) / 1000)}s`);
const status = await (await admin.get("/api/v1/system/ai-status")).json();
log("AI status:", status.sync_status, status.active_regulation_version, "|", status.current_step_label);
await page.getByLabel(/email/i).first().fill("trong.tran@eas.com");
await page.locator('input[type="password"]').first().fill(PASSWORD);
await submit.click();
await page.getByRole("navigation", { name: "Điều hướng chính" }).waitFor();
await page.waitForTimeout(2500);
const dialogs = await page.locator("dialog[open]").count();
log("employee back in; failure notice shown to employee:", dialogs ? await page.locator("dialog[open]").getAttribute("aria-label") : "none");
await browser.close();
await admin.dispose();
