// Walks every sidebar page of both portals against a running local stack
// (Vite :5173/:5174 -> Django :8000). Usage: node e2e/live_stack_walk.mjs
import { chromium } from "@playwright/test";

const PORTALS = [
  { name: "admin", url: process.env.EAS_ADMIN_URL || "http://localhost:5174", email: "admin@eas.com", password: process.env.EAS_ADMIN_PASSWORD },
  { name: "client", url: process.env.EAS_CLIENT_URL || "http://localhost:5173", email: process.env.EAS_CLIENT_EMAIL || "trong.tran@eas.com" },
];
const PASSWORD = process.env.EAS_PASSWORD || "Password@123456";
const problems = [];

const browser = await chromium.launch();
for (const portal of PORTALS) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  page.on("console", (m) => m.type() === "error" && problems.push(`${portal.name} console: ${m.text().slice(0, 160)}`));
  page.on("pageerror", (e) => problems.push(`${portal.name} pageerror: ${e.message.slice(0, 160)}`));
  page.on("response", (r) => {
    if (r.status() >= 500) problems.push(`${portal.name} HTTP ${r.status()} ${r.url()}`);
    if ([401, 403, 503].includes(r.status())) console.log(`${portal.name} HTTP ${r.status()} ${r.request().method()} ${r.url().replace(/^https?:\/\/[^/]+/, "")}`);
  });
  await page.goto(portal.url);
  await page.getByLabel(/email/i).first().fill(portal.email);
  await page.locator('input[type="password"]').first().fill(portal.password || PASSWORD);
  const announcements = page.waitForResponse((r) => r.url().includes("/api/v1/announcements"), { timeout: 30000 }).catch(() => null);
  await page.locator('button[type="submit"]').first().click();
  await page.getByRole("navigation", { name: "Điều hướng chính" }).waitFor({ timeout: 30000 });
  // Unread system updates open a dialog after sign-in.
  await announcements;
  await page.waitForTimeout(500);
  const dialog = page.locator("dialog[open]");
  if (await dialog.count()) {
    console.log(`${portal.name}: update dialog "${await dialog.getAttribute("aria-label")}"`);
    while (await page.locator("dialog[open]").count()) {
      await page.locator("dialog[open]").getByRole("button", { name: /Đã hiểu/ }).click();
    }
  }
  const nav = page.getByRole("navigation", { name: "Điều hướng chính" });
  const items = nav.locator("button.nav-item");
  const count = await items.count();
  let previous = (await page.locator("main h1").first().innerText().catch(() => "")).trim();
  for (let i = 0; i < count; i += 1) {
    const label = (await items.nth(i).locator(".nav-text").innerText().catch(() => `#${i}`)).trim();
    while (await page.locator("dialog[open]").count()) {
      console.log(`${portal.name}: update dialog "${await page.locator("dialog[open]").getAttribute("aria-label")}"`);
      await page.locator("dialog[open]").getByRole("button", { name: /Đã hiểu/ }).click();
    }
    await items.nth(i).click({ timeout: 10000 }).catch(async (e) => {
      await page.screenshot({ path: `test-results/live-${portal.name}-stuck.png` });
      throw e;
    });
    // Live data is slower: wait until the heading changes or the page settles.
    await page.waitForFunction((prev) => (document.querySelector("main h1")?.innerText || "").trim() !== prev, previous, { timeout: 8000 }).catch(() => {});
    await page.waitForLoadState("networkidle").catch(() => {});
    const h1 = (await page.locator("main h1").first().innerText().catch(() => "")).trim();
    previous = h1;
    const denied = await page.locator(".access-denied-view").count();
    const failed = await page.locator("text=/Không thể tải|Lỗi tải|Something went wrong/").count();
    console.log(`${portal.name} | ${label.padEnd(30)} | h1="${h1.slice(0, 40)}"${denied ? " | ACCESS DENIED" : ""}${failed ? " | LOAD ERROR" : ""}`);
    if (denied || failed) problems.push(`${portal.name} page "${label}" denied=${denied} loadError=${failed}`);
  }
  await page.screenshot({ path: `test-results/live-${portal.name}-last.png` });
  await page.close();
}
await browser.close();
console.log(problems.length ? `\nPROBLEMS (${problems.length}):\n- ${[...new Set(problems)].join("\n- ")}` : "\nNO PROBLEMS");
