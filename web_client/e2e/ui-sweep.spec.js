import { test, expect } from "@playwright/test";

// Visits every navigation page of both portals with a mocked API and reports
// display defects: horizontal overflow, runtime errors, leaked placeholder
// values ("undefined", "NaN", "[object Object]") and missing page headings.
// Screenshots go to test-results/ui-sweep/ for visual review.
const CLIENT = "http://127.0.0.1:4173";
const ADMIN = "http://127.0.0.1:4174";
const ME = "22222222-2222-4222-8222-222222222222";
const MODULES = ["dashboard", "requests_workflows", "users", "regulations", "ai_engine", "api_management", "org_chart", "permissions", "system_versions"];
const ALL = { can_view: true, can_create: true, can_edit: true, can_delete: true };
const permissions = { by_module: Object.fromEntries(MODULES.map((m) => [m, ALL])) };

const USERS = {
  client: { email: "anh@eas.com", roles: ["REQUESTER", "APPROVER", "EXECUTOR", "ACCEPTOR"], capabilities: {}, permissions },
  admin: { email: "admin@eas.com", roles: ["OPS_ADMIN", "POLICY_ADMIN"], capabilities: { identity_manage: true }, permissions },
};

async function mock(page, kind) {
  const user = { id: ME, display_name: "Nguyễn Minh Anh", department_id: "d1", department_name: "Phòng Kế toán", ...USERS[kind] };
  await page.route(/\/(api\/v1|health)\//, (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/^\/api\/v1\//, "");
    const send = (value) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(value) });
    if (url.pathname === "/health/ready") return send({ status: "ready", checks: { database: true } });
    if (path === "auth/csrf") return send({});
    if (path === "auth/me") return send({ user });
    if (path === "notifications") return send({ items: [], unread_count: 0, next_offset: null });
    // Empty-but-valid payloads exercise every empty state.
    return send({ items: [], next_offset: null, departments: [], users: [], report: {}, revisions: [] });
  });
}

const LEAK = /\bundefined\b|\bNaN\b|\[object Object\]|Invalid Date/;

for (const [kind, base] of [["client", CLIENT], ["admin", ADMIN]]) {
  for (const width of [1440, 375]) {
    test(`${kind} sweep at ${width}px`, async ({ page }) => {
      test.setTimeout(180000);
      const issues = [];
      page.on("pageerror", (err) => issues.push(`runtime error: ${err.message.split("\n")[0]}`));
      await page.setViewportSize({ width, height: width < 600 ? 812 : 900 });
      await mock(page, kind);
      await page.goto(base);
      await page.locator(".app-shell").waitFor();
      const openNav = async () => {
        if (width < 900) await page.getByRole("button", { name: "Mở điều hướng" }).click();
      };
      await openNav();
      const labels = await page.locator(".sidebar-nav .nav-item .nav-text").allInnerTexts();
      if (width < 900) await page.keyboard.press("Escape");
      expect(labels.length).toBeGreaterThan(0);
      for (const label of labels) {
        console.log(`[sweep] ${kind} ${width} -> ${label}`);
        if (!(await page.locator(".app-shell").count())) {
          await page.goto(base);
          await page.locator(".app-shell").waitFor();
        }
        await openNav();
        await page.locator(".sidebar-nav .nav-item", { hasText: label }).first().click();
        await page.waitForTimeout(450);
        if (await page.getByRole("heading", { name: "Đã xảy ra sự cố hiển thị" }).count()) {
          issues.push(`${label}: page crashed (error boundary shown)`);
          await page.goto(base);
          await page.locator(".app-shell").waitFor();
          continue;
        }
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
        if (overflow > 1) issues.push(`${label}: horizontal overflow ${overflow}px`);
        const text = await page.locator("main").innerText();
        const leak = text.match(LEAK);
        if (leak) issues.push(`${label}: leaked "${leak[0]}" in "${text.slice(Math.max(0, leak.index - 40), leak.index + 20).replace(/\s+/g, " ")}"`);
        if (!(await page.locator("main h1").count())) issues.push(`${label}: no page heading`);
        const slug = label.normalize("NFD").replace(/\p{M}/gu, "").replace(/đ/gi, "d").replace(/[^a-z0-9]+/gi, "-").toLowerCase();
        await page.screenshot({ path: `test-results/ui-sweep/${kind}-${width}-${slug}.png` });
      }
      expect(issues, issues.join("\n")).toEqual([]);
    });
  }
}
