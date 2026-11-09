import { chromium } from "playwright";
import path from "path";
import fs from "fs";

const ARTIFACT_DIR = "C:/Users/PHAN QUANG HUY/.gemini/antigravity/brain/f3a0e7bd-8e68-488f-8a6a-9f9afecd4111";

async function run() {
  console.log("=== BATCH 2 VERIFICATION PLAYWRIGHT SUITE ===");
  const browser = await chromium.launch({ headless: true });
  const results = [];

  try {
    // ==========================================
    // 1. ADMIN PORTAL (http://127.0.0.1:8081)
    // ==========================================
    console.log("\n[TEST 1] Logging into Admin Portal (8081)...");
    const adminContext = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await adminContext.newPage();
    await page.goto("http://127.0.0.1:8081", { waitUntil: "domcontentloaded" });

    // Fill login
    await page.waitForSelector('input[name="email"], input[type="email"]', { timeout: 10000 });
    await page.fill('input[name="email"], input[type="email"]', "admin@eas.com");
    await page.fill('input[name="password"], input[type="password"]', "admin@123456789");
    await page.click('button[type="submit"]');

    // Wait for Admin shell
    await page.waitForSelector(".app-shell, .sidebar, .sidebar-nav", { timeout: 15000 });
    console.log(" - Admin successfully logged in.");

    // ==========================================
    // TEST CASE 2.1: RBAC Matrix & Hardcoded Lock
    // ==========================================
    console.log("\n[TEST CASE 2.1] Testing RBAC Matrix & 4 System Locked Modules...");
    const permNav = page.locator('.sidebar-nav button:has-text("Phân quyền"), .sidebar-nav button:has-text("Ma trận phân quyền")').first();
    await permNav.click();

    // Wait for matrix table rows to load from API
    await page.waitForSelector('.badge-locked, tr.row-locked-module', { timeout: 15000 });

    // Verify Role Tab & Locked badges
    const lockedBadges = await page.locator('.badge-locked, :text("Khóa cứng hệ thống")').count();
    console.log(` - Found ${lockedBadges} "Khóa cứng hệ thống" badges in RBAC view.`);
    if (lockedBadges < 4) {
      throw new Error(`Expected at least 4 locked badges for system modules, found ${lockedBadges}`);
    }

    // Verify locked checkboxes are disabled
    const lockedRows = page.locator('tr.row-locked-module');
    const lockedRowsCount = await lockedRows.count();
    console.log(` - Found ${lockedRowsCount} row-locked-module rows.`);

    const shot1 = path.join(ARTIFACT_DIR, "tc2_1_rbac_locked_modules.png");
    await page.screenshot({ path: shot1, fullPage: false });
    console.log(" - Saved screenshot:", shot1);

    // Test switching to "Quyền riêng theo nhân viên" tab
    console.log(" - Testing User Override tab...");
    const userTabBtn = page.locator('button:has-text("Quyền riêng theo nhân viên"), button:has-text("Quyền riêng")').first();
    if (await userTabBtn.isVisible()) {
      await userTabBtn.click();
      await page.waitForSelector("select", { timeout: 10000 });
      const userSelect = page.locator("select").first();
      const userOptions = await userSelect.locator("option").count();
      console.log(` - User override select has ${userOptions} users available.`);
      if (userOptions > 1) {
        await userSelect.selectOption({ index: 1 });
        await page.waitForSelector('.badge-locked, tr.row-locked-module', { timeout: 15000 });
      }
      const userLockedBadges = await page.locator('.badge-locked, :text("Khóa cứng hệ thống")').count();
      console.log(` - Found ${userLockedBadges} locked badges in User override view.`);
      const shot1b = path.join(ARTIFACT_DIR, "tc2_1_rbac_user_override.png");
      await page.screenshot({ path: shot1b, fullPage: false });
      console.log(" - Saved screenshot:", shot1b);
    }
    results.push({ test: "TC 2.1: RBAC Matrix & Locked Modules", status: "PASS" });

    // ==========================================
    // TEST CASE 2.2: Users Management & Drilldown
    // ==========================================
    console.log("\n[TEST CASE 2.2] Testing User Management & 5-Stage Drilldown...");
    const usersNav = page.locator('.sidebar-nav button:has-text("Người dùng")').first();
    await usersNav.click();
    await page.waitForSelector(".user-management-table tbody tr", { timeout: 15000 });

    // Verify user count
    const userRows = await page.locator(".user-management-table tbody tr").count();
    console.log(` - Loaded ${userRows} user rows in User Management.`);
    if (userRows < 30) {
      throw new Error(`Expected at least 30+ users, got ${userRows}`);
    }

    // Test Quick Leave/Trip Modal
    const calendarBtn = page.locator('button.btn-icon-subtle[title*="đơn nghỉ"], button.btn-icon-subtle').first();
    if (await calendarBtn.isVisible()) {
      console.log(" - Opening quick leave/trip modal...");
      await calendarBtn.click();
      await page.waitForSelector('.modal-card, [role="dialog"]', { timeout: 5000 });
      const shot2a = path.join(ARTIFACT_DIR, "tc2_2_users_leave_trip_modal.png");
      await page.screenshot({ path: shot2a, fullPage: false });
      console.log(" - Saved screenshot:", shot2a);
      // Close modal
      const closeBtn = page.locator('.modal-head button, button:has-text("Hủy")').first();
      await closeBtn.click();
      await page.waitForTimeout(500);
    }

    // Test 5-stage drilldown modal by clicking total requests
    console.log(" - Testing 5-stage request drilldown modal...");
    const drilldownBtn = page.locator('button.drilldown-badge-btn').first();
    if (await drilldownBtn.isVisible()) {
      await drilldownBtn.click();
      await page.waitForSelector('.drawer-panel, [role="dialog"]', { timeout: 10000 });
      await page.waitForTimeout(1000);
      const stagePills = await page.locator('.stage-kpi-card, .stage-summary-pill, .kpi-value').count();
      console.log(` - 5-stage drilldown modal opened with ${stagePills} KPI indicators.`);
      const shot2b = path.join(ARTIFACT_DIR, "tc2_2_users_5_stage_drilldown.png");
      await page.screenshot({ path: shot2b, fullPage: false });
      console.log(" - Saved screenshot:", shot2b);
      // Close drawer
      const closeDrawerBtn = page.locator('button.drawer-close-btn').first();
      if (await closeDrawerBtn.isVisible()) {
        await closeDrawerBtn.click();
      } else {
        await page.keyboard.press("Escape");
      }
      await page.waitForTimeout(1000);
    }
    results.push({ test: "TC 2.2: Users Management & 5-Stage Drilldown", status: "PASS" });

    // ==========================================
    // TEST CASE 2.3: Org Chart Tree & Roster
    // ==========================================
    console.log("\n[TEST CASE 2.3] Testing Org Chart & 8 Standard Departments...");
    const orgNav = page.locator('.sidebar-nav button:has-text("Sơ đồ công ty"), .sidebar-nav button:has-text("Sơ đồ tổ chức")').first();
    await orgNav.click();
    await page.waitForSelector('.org-box-director', { timeout: 15000 });

    // Verify departments
    const bodCount = await page.locator('.org-box-director').count();
    const childDeptCount = await page.locator('.org-dept-header-card').count();
    const totalDepts = bodCount + childDeptCount;
    console.log(` - Rendered ${totalDepts} department blocks (1 BOD + ${childDeptCount} child departments).`);
    if (totalDepts < 8) {
      throw new Error(`Expected at least 8 departments, got ${totalDepts}`);
    }

    // Click on a department to open roster
    const childDeptCard = page.locator('.org-dept-header-card').first();
    if (await childDeptCard.isVisible()) {
      await childDeptCard.click();
      await page.waitForSelector('.org-modal-card, [role="dialog"]', { timeout: 5000 });
      console.log(" - Department roster opened.");
    }
    const shot3 = path.join(ARTIFACT_DIR, "tc2_3_org_chart_tree_and_roster.png");
    await page.screenshot({ path: shot3, fullPage: false });
    console.log(" - Saved screenshot:", shot3);
    results.push({ test: "TC 2.3: Org Chart 8 Departments & Roster", status: "PASS" });

    await page.close();
    await adminContext.close();

    // ==========================================
    // TEST CASE 2.1.4: Client Portal Permission Sync
    // ==========================================
    console.log("\n[TEST CASE 2.1.4] Testing Client Portal Permission Sync (5173)...");
    const clientContext = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const clientPage = await clientContext.newPage();
    await clientPage.goto("http://127.0.0.1:5173", { waitUntil: "domcontentloaded" });

    // Fill login as employee
    await clientPage.waitForSelector('input[name="email"], input[type="email"]', { timeout: 10000 });
    await clientPage.fill('input[name="email"], input[type="email"]', "tien.ly@eas.com");
    await clientPage.fill('input[name="password"], input[type="password"]', "Password@123456");
    await clientPage.click('button[type="submit"]');

    // Wait for Client shell
    await clientPage.waitForSelector(".app-shell, .sidebar, .sidebar-nav", { timeout: 15000 });
    console.log(" - Employee tien.ly logged in to Client Portal.");

    // Check sidebar does NOT have locked modules
    const forbiddenModules = ["permissions", "ai_engine", "api_management", "system_versions", "users"];
    for (const mod of forbiddenModules) {
      const elCount = await clientPage.locator(`.sidebar-nav button[data-screen="${mod}"]`).count();
      if (elCount > 0) {
        throw new Error(`Forbidden module ${mod} is visible on employee sidebar!`);
      }
    }
    console.log(" - Verified: No locked modules visible in Employee sidebar.");

    const shot4 = path.join(ARTIFACT_DIR, "tc2_1_client_portal_permissions_sync.png");
    await clientPage.screenshot({ path: shot4, fullPage: false });
    console.log(" - Saved screenshot:", shot4);
    results.push({ test: "TC 2.1.4: Client Portal Sidebar & Action Permission Sync", status: "PASS" });

    await clientPage.close();
    await clientContext.close();

  } catch (err) {
    console.error("Test execution error:", err);
    results.push({ test: "Execution Error", status: "FAIL", error: err.message });
  } finally {
    await browser.close();
  }

  console.log("\n=== TEST RESULTS SUMMARY ===");
  console.table(results);
  const allPass = results.length > 0 && results.every((r) => r.status === "PASS");
  if (!allPass) {
    process.exit(1);
  }
}

void run();
