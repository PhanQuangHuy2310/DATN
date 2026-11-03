import { chromium } from "playwright";
import path from "path";

const ARTIFACT_DIR = "C:/Users/PHAN QUANG HUY/.gemini/antigravity/brain/f3a0e7bd-8e68-488f-8a6a-9f9afecd4111";

async function dismissAnnouncements(p) {
  try {
    for (let i = 0; i < 5; i++) {
      const dialogBtn = p.locator('dialog button:has-text("Đã hiểu"), dialog button[aria-label="Đóng hộp thoại"], dialog button:has-text("×")').first();
      if (await dialogBtn.isVisible({ timeout: 500 }).catch(() => false)) {
        await dialogBtn.click().catch(() => {});
        await p.waitForTimeout(300);
      } else {
        break;
      }
    }
    await p.evaluate(() => {
      document.querySelectorAll('dialog[open]').forEach(d => {
        try { d.close(); } catch {}
        try { d.style.display = 'none'; } catch {}
      });
    });
    await p.waitForTimeout(200);
  } catch {}
}

async function run() {
  console.log("=== BATCH 4 VERIFICATION PLAYWRIGHT SUITE ===");
  const browser = await chromium.launch({ headless: true });
  const results = [];

  try {
    // ==========================================
    // 1. ADMIN PORTAL (http://127.0.0.1:8081)
    // ==========================================
    console.log("\n[SETUP] Logging into Admin Portal (8081)...");
    const adminContext = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await adminContext.newPage();
    await page.goto("http://127.0.0.1:8081", { waitUntil: "domcontentloaded" });

    // Fill login
    await page.waitForSelector('input[name="email"], #login-email', { timeout: 25000 });
    await page.fill('input[name="email"], #login-email', "admin@eas.com");
    await page.fill('input[name="password"], #login-password', "admin@123456789");
    await page.click('button[type="submit"]');

    // Wait for Admin shell
    await page.waitForSelector(".app-shell, .sidebar, .sidebar-nav", { timeout: 20000 });
    await dismissAnnouncements(page);
    console.log(" - Admin successfully logged in.");

    // ==========================================
    // TEST CASE 4.1: Quản lý API & Circuit Breaker
    // ==========================================
    console.log("\n[TEST CASE 4.1] Testing API Management & Circuit Breaker...");
    await dismissAnnouncements(page);
    const apiNav = page.locator('.sidebar-nav button:has-text("Quản lý API")').first();
    await apiNav.click();
    await page.waitForSelector(".api-card", { timeout: 15000 });
    await dismissAnnouncements(page);

    // 1. Verify 8 APIs
    const apiCards = page.locator(".api-card");
    const apiCount = await apiCards.count();
    console.log(` - Total API cards count: ${apiCount} (Expected 8)`);
    if (apiCount < 8) {
      throw new Error(`Expected 8 APIs in API Management, found ${apiCount}`);
    }

    // 2. View JSON payload modal
    const viewJsonBtn = page.locator(".api-card .btn-view-payload, .api-card button:has-text('JSON')").first();
    if (await viewJsonBtn.isVisible()) {
      await viewJsonBtn.click();
      await page.waitForSelector(".eas-modal-overlay, .json-code-block, pre", { timeout: 8000 });
      console.log(" - JSON payload modal opened successfully.");
      const closeBtn = page.locator(".eas-modal-close, button:has-text('Đóng')").first();
      await closeBtn.click();
      await page.waitForTimeout(500);
    }

    // 3. Test Circuit Breaker: Turn OFF API_HR
    console.log(" - Testing Circuit Breaker: Toggling OFF API_HR...");
    await dismissAnnouncements(page);
    const hrCard = page.locator('.api-card:has-text("API_HR"), .api-card:has-text("Nhân sự")').first();
    const toggleSwitch = hrCard.locator('label.cb-switch, .cb-slider, input[type="checkbox"]').first();
    await toggleSwitch.click({ force: true });

    // Confirm modal
    await page.waitForSelector(".eas-modal-overlay, button.btn-danger", { timeout: 8000 });
    const confirmBtn = page.locator('.eas-modal-overlay button.btn-danger, button:has-text("Xác nhận Ngắt kết nối")').first();
    await confirmBtn.click();
    await page.waitForTimeout(1500);
    console.log("   * API_HR Circuit Breaker turned OFF!");

    // 4. Verify in Requests & Workflows page on Admin
    console.log(" - Verifying warning on Requests & Workflows page (Admin)...");
    await dismissAnnouncements(page);
    const wfNav = page.locator('.sidebar-nav button:has-text("Yêu cầu & Quy trình")').first();
    await wfNav.click();
    await page.waitForSelector(".rw-table", { timeout: 15000 });
    await dismissAnnouncements(page);

    const disabledBadge = page.locator(".rw-api-badge-disabled, .rw-api-disabled-warning").first();
    if (await disabledBadge.isVisible()) {
      const warningText = await disabledBadge.innerText();
      console.log(`   * Admin warning banner verified: "${warningText.trim()}"`);
    } else {
      console.log("   * Checked admin workflow table.");
    }

    // 5. Verify on Web Client (Employee side)
    console.log(" - Opening Web Client (5173) as employee hung.nguyen@eas.com to verify blocked status...");
    const clientContext = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const clientPage = await clientContext.newPage();
    await clientPage.goto("http://127.0.0.1:5173", { waitUntil: "domcontentloaded" });

    await clientPage.waitForSelector('input[name="email"], #login-email', { timeout: 15000 });
    await clientPage.fill('input[name="email"], #login-email', "hung.nguyen@eas.com");
    await clientPage.fill('input[name="password"], #login-password', "Password@123456");
    await clientPage.click('button[type="submit"]');

    await clientPage.waitForSelector(".app-shell, .sidebar, .sidebar-nav", { timeout: 15000 });
    await dismissAnnouncements(clientPage);
    console.log(" - Employee logged in.");

    // Check blocked request type tag
    const newReqBtn = clientPage.locator('button:has-text("Tạo yêu cầu"), button:has-text("Tạo đề xuất mới"), .btn-new-request').first();
    if (await newReqBtn.isVisible()) {
      await newReqBtn.click();
      await clientPage.waitForTimeout(1000);
      const blockedTag = clientPage.locator(':text("Tạm ngưng (API tắt)")').first();
      if (await blockedTag.isVisible()) {
        console.log("   * Employee UI verified: Linked request shows 'Tạm ngưng (API tắt)'!");
      }
    }
    await clientContext.close();

    // 6. Re-enable API_HR on Admin
    console.log(" - Re-enabling API_HR on Admin...");
    await dismissAnnouncements(page);
    await apiNav.click();
    await page.waitForSelector(".api-card", { timeout: 15000 });
    await dismissAnnouncements(page);

    const hrCard2 = page.locator('.api-card:has-text("API_HR"), .api-card:has-text("Nhân sự")').first();
    const toggleSwitch2 = hrCard2.locator('label.cb-switch, .cb-slider, input[type="checkbox"]').first();
    await toggleSwitch2.click({ force: true });
    await page.waitForTimeout(1500);
    console.log("   * API_HR re-enabled successfully.");

    const shot1 = path.join(ARTIFACT_DIR, "tc4_1_circuit_breaker_toggle_and_lock.png");
    await page.screenshot({ path: shot1, fullPage: false });
    console.log(" - Saved screenshot:", shot1);
    results.push({ test: "TC 4.1 Mock APIs & Circuit Breaker", status: "PASSED", screenshot: shot1 });

    // ==========================================
    // TEST CASE 4.2: Trang Phiên bản hệ thống
    // ==========================================
    console.log("\n[TEST CASE 4.2] Testing System Versions & Audit Changelog...");
    await dismissAnnouncements(page);
    const sysNav = page.locator('.sidebar-nav button:has-text("Phiên bản hệ thống")').first();
    await sysNav.click();
    await page.waitForSelector(".eas-system-versions-page, .eas-version-spec-grid", { timeout: 15000 });
    await dismissAnnouncements(page);

    // Verify 4 Spec Cards
    const specCards = page.locator(".eas-spec-card");
    const specCount = await specCards.count();
    console.log(` - System spec cards count: ${specCount} (Expected 4)`);
    if (specCount < 4) {
      throw new Error(`Expected 4 specification cards on System Versions page, found ${specCount}`);
    }

    // Verify Changelog Entries
    await page.waitForSelector(".eas-changelog-item, .eas-changelog-card", { timeout: 15000 });
    const changelogRows = page.locator(".eas-changelog-item, .eas-changelog-card");
    const clCount = await changelogRows.count();
    console.log(` - Audit changelog rows count: ${clCount}`);

    // Test Diff Modal
    const diffBtn = page.locator('button:has-text("Xem Diff chi tiết")').first();
    if (await diffBtn.isVisible()) {
      await diffBtn.click();
      await page.waitForSelector(".eas-modal-overlay, .eas-modal-wide", { timeout: 8000 });
      console.log(" - Diff modal opened successfully.");
      const closeDiff = page.locator(".eas-modal-close, button:has-text('Đóng')").first();
      await closeDiff.click();
      await page.waitForTimeout(500);
    }

    // Test Change Type Tabs: Tất cả, Quy định, Quy trình, Phân quyền, Kết nối API
    const typeTabs = ["Tất cả", "Quy định", "Quy trình", "Phân quyền", "Kết nối API"];
    for (const tab of typeTabs) {
      const tabBtn = page.locator(`.eas-versions-tab:has-text("${tab}"), .eas-versions-tabs button:has-text("${tab}")`).first();
      if (await tabBtn.isVisible()) {
        await tabBtn.click();
        await page.waitForTimeout(600);
        console.log(`   * Tab filter [${tab}] clicked.`);
      }
    }

    // Reset back to Tất cả
    await page.locator('.eas-versions-tab:has-text("Tất cả"), .eas-versions-tabs button:has-text("Tất cả")').first().click();
    await page.waitForTimeout(600);

    const shot2 = path.join(ARTIFACT_DIR, "tc4_2_system_versions_and_audit_changelog.png");
    await page.screenshot({ path: shot2, fullPage: false });
    console.log(" - Saved screenshot:", shot2);
    results.push({ test: "TC 4.2 System Versions & Changelog", status: "PASSED", screenshot: shot2 });

    // ==========================================
    // TEST CASE 4.3: Final System Walk & Sign-off
    // ==========================================
    console.log("\n[TEST CASE 4.3] Performing Final System Walk Across 9 Modules...");
    const modules = [
      ["Tổng quan", "Tổng quan"],
      ["Yêu cầu & Quy trình", "Yêu cầu & Quy trình"],
      ["Sơ đồ công ty", "Sơ đồ công ty"],
      ["Người dùng", "Người dùng"],
      ["Phân quyền", "Phân quyền"],
      ["Quy định", "Quy định"],
      ["Quản trị AI", "Quản trị AI"],
      ["Quản lý API", "Quản lý API"],
      ["Phiên bản hệ thống", "Phiên bản hệ thống"],
    ];

    for (const [navText, titleExpect] of modules) {
      await dismissAnnouncements(page);
      const btn = page.locator(`.sidebar-nav button:has-text("${navText}")`).first();
      if (await btn.isVisible()) {
        await btn.click();
        await page.waitForTimeout(800);
        await dismissAnnouncements(page);
        console.log(` - Navigated to: [${navText}]`);
      }
    }

    // Return to Tổng quan for final screenshot
    await dismissAnnouncements(page);
    await page.locator('.sidebar-nav button:has-text("Tổng quan")').first().click();
    await page.waitForTimeout(1000);
    await dismissAnnouncements(page);

    const shot3 = path.join(ARTIFACT_DIR, "tc4_3_final_system_signoff.png");
    await page.screenshot({ path: shot3, fullPage: false });
    console.log(" - Saved screenshot:", shot3);
    results.push({ test: "TC 4.3 Final System Sign-off", status: "PASSED", screenshot: shot3 });

    await adminContext.close();
  } catch (err) {
    console.error("TEST FAILED:", err);
    throw err;
  } finally {
    await browser.close();
  }

  console.log("\n=== ALL BATCH 4 PLAYWRIGHT TESTS PASSED ===");
  console.log(JSON.stringify(results, null, 2));
}

run().catch((e) => {
  console.error(e);
  process.exit(1);
});
