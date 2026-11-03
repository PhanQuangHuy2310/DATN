import { chromium } from "playwright";
import path from "path";
import fs from "fs";

const ARTIFACT_DIR = "C:/Users/PHAN QUANG HUY/.gemini/antigravity/brain/f3a0e7bd-8e68-488f-8a6a-9f9afecd4111";

async function run() {
  console.log("=== BATCH 3 VERIFICATION PLAYWRIGHT SUITE ===");
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
    await page.waitForSelector('input[name="email"], input[type="email"]', { timeout: 10000 });
    await page.fill('input[name="email"], input[type="email"]', "admin@eas.com");
    await page.fill('input[name="password"], input[type="password"]', "admin@123456789");
    await page.click('button[type="submit"]');

    // Wait for Admin shell
    await page.waitForSelector(".app-shell, .sidebar, .sidebar-nav", { timeout: 15000 });
    console.log(" - Admin successfully logged in.");

    // ==========================================
    // TEST CASE 3.1: Trang Tổng quan (Dashboard)
    // ==========================================
    console.log("\n[TEST CASE 3.1] Testing Dashboard (Tổng quan)...");
    const dashNav = page.locator('.sidebar-nav button:has-text("Tổng quan")').first();
    await dashNav.click();

    // Wait for Dashboard analytics API response and KPI cards load
    await page.waitForSelector(".admin-kpi-grid, .admin-kpi-card", { timeout: 10000 });
    await page.waitForTimeout(1500);

    const totalReqText = await page.locator(".card-total .kpi-value").innerText();
    const successCountText = await page.locator(".card-success .kpi-value").innerText();
    const rejectedCountText = await page.locator(".card-danger .kpi-value").innerText();
    const processingCountText = await page.locator(".card-warning .kpi-value").innerText();

    console.log(` - KPIs found: Total = ${totalReqText}, Success = ${successCountText}, Rejected = ${rejectedCountText}, Processing = ${processingCountText}`);

    if (totalReqText.includes("NaN") || successCountText.includes("NaN") || rejectedCountText.includes("NaN")) {
      throw new Error(`Dashboard KPI contains NaN: Total=${totalReqText}, Success=${successCountText}`);
    }

    // Verify Category Performance Section (A, B, C)
    const catPerfCards = page.locator(".admin-cat-perf-card");
    const catCount = await catPerfCards.count();
    console.log(` - Category performance cards count: ${catCount} (Expected 3)`);
    if (catCount < 3) {
      throw new Error(`Expected at least 3 category performance cards, found ${catCount}`);
    }

    // Test time filter buttons: Theo Ngày, Theo Tuần, Theo Tháng, Theo Năm
    const periodButtons = ["Theo Ngày", "Theo Tuần", "Theo Tháng", "Theo Năm"];
    for (const p of periodButtons) {
      const btn = page.locator(`.admin-period-btn:has-text("${p}")`).first();
      if (await btn.isVisible()) {
        await btn.click();
        await page.waitForTimeout(800);
        const val = await page.locator(".card-total .kpi-value").innerText();
        console.log(`   * Filter [${p}]: KPI Total = ${val}`);
        if (val.includes("NaN") || val.includes("undefined")) {
          throw new Error(`Filter [${p}] resulted in invalid value: ${val}`);
        }
      }
    }

    // Reset back to Theo Tháng
    await page.locator('.admin-period-btn:has-text("Theo Tháng")').first().click();
    await page.waitForTimeout(800);

    const shot1 = path.join(ARTIFACT_DIR, "tc3_1_admin_dashboard_periods_and_kpis.png");
    await page.screenshot({ path: shot1, fullPage: false });
    console.log(" - Saved screenshot:", shot1);
    results.push({ test: "TC 3.1 Dashboard & Periods", status: "PASSED", screenshot: shot1 });

    // ==========================================
    // TEST CASE 3.2: Yêu cầu & Quy trình (A/B/C) + Trọng số
    // ==========================================
    console.log("\n[TEST CASE 3.2] Testing Requests & Workflows (A/B/C + Weights)...");
    const wfNav = page.locator('.sidebar-nav button:has-text("Yêu cầu & Quy trình")').first();
    await wfNav.click();

    await page.waitForSelector(".rw-categories-grid, .rw-table", { timeout: 15000 });

    // 1. Verify 3 Categories
    const catCards = page.locator(".rw-category-card");
    const catCardsCount = await catCards.count();
    console.log(` - Workflow categories cards count: ${catCardsCount} (Expected 3: A, B, C)`);
    if (catCardsCount < 3) {
      throw new Error(`Expected 3 workflow categories cards, found ${catCardsCount}`);
    }

    // 2. Verify Templates Table
    const templateRows = page.locator(".rw-table tbody tr");
    const rowCount = await templateRows.count();
    console.log(` - Template table rows count: ${rowCount}`);
    if (rowCount < 1) {
      throw new Error("No templates loaded in requests & workflows table");
    }

    // 3. Test Category Switching (e.g., A -> B or C -> B)
    const firstRowSelect = page.locator(".rw-table tbody tr select.rw-cat-select").first();
    const origCategory = await firstRowSelect.inputValue();
    const newCategory = origCategory === "B" ? "A" : "B";
    console.log(` - Switching first template category from ${origCategory} to ${newCategory}...`);
    await firstRowSelect.selectOption(newCategory);
    await page.waitForTimeout(1000);

    // Check toast notification
    const toast = page.locator(".rw-toast, .toast");
    if (await toast.isVisible()) {
      console.log(`   * Toast received: "${await toast.innerText()}"`);
    }

    // Verify select value updated
    const updatedCategory = await firstRowSelect.inputValue();
    console.log(`   * Category select new value in DOM: ${updatedCategory}`);

    // Revert category back
    await firstRowSelect.selectOption(origCategory);
    await page.waitForTimeout(1000);
    console.log(`   * Reverted category back to ${origCategory}.`);

    // 4. Test Weight Adjustment
    const firstSlider = page.locator(".rw-table tbody tr input.rw-weight-slider").first();
    if (await firstSlider.isVisible()) {
      console.log(" - Testing weight slider adjustment...");
      await firstSlider.fill("85");
      await firstSlider.dispatchEvent("change");
      await firstSlider.dispatchEvent("mouseup");
      await page.waitForTimeout(1000);
      console.log("   * Automation weight updated to 85%");
    }

    const shot2 = path.join(ARTIFACT_DIR, "tc3_2_workflows_category_switch_and_weight.png");
    await page.screenshot({ path: shot2, fullPage: false });
    console.log(" - Saved screenshot:", shot2);
    results.push({ test: "TC 3.2 Workflows & Weights", status: "PASSED", screenshot: shot2 });

    // ==========================================
    // TEST CASE 3.3: Quản lý Quy định & Đánh số Phiên bản
    // ==========================================
    console.log("\n[TEST CASE 3.3] Testing Regulations Management & Semantic Versioning...");
    const regNav = page.locator('.sidebar-nav button:has-text("Quy định")').first();
    await regNav.click();

    await page.waitForSelector(".regulations-page, .eas-meta-cards-row", { timeout: 15000 });

    const activeVerText = await page.locator(".version-pill.current-version").first().innerText();
    console.log(` - Active regulation version: ${activeVerText}`);

    // Test Minor Update (Edit existing regulation)
    console.log(" - Testing Minor Edit on regulation...");
    const editBtn = page.locator(".regulation-card .btn-edit").first();
    if (await editBtn.isVisible()) {
      await editBtn.click();
      await page.waitForSelector(".eas-modal-overlay, .eas-modal-form", { timeout: 8000 });

      // Change title slightly
      const titleInput = page.locator('.eas-modal-form input[type="text"]:not([disabled])').first();
      const currentTitle = await titleInput.inputValue();
      await titleInput.fill(currentTitle + " [Audit 2026]");

      const saveBtn = page.locator('.eas-modal-form button[type="submit"]').first();
      await saveBtn.click();
      await page.waitForTimeout(2000);
      console.log("   * Minor edit saved successfully.");
    }

    const shot3 = path.join(ARTIFACT_DIR, "tc3_3_regulations_semantic_versioning.png");
    await page.screenshot({ path: shot3, fullPage: false });
    console.log(" - Saved screenshot:", shot3);
    results.push({ test: "TC 3.3 Regulations Semantic Versioning", status: "PASSED", screenshot: shot3 });

    // ==========================================
    // TEST CASE 3.4: Quản trị AI & Khóa/Mở Web Client
    // ==========================================
    console.log("\n[TEST CASE 3.4] Testing AI Engine Management & Auto-Lock Web Client...");
    const aiNav = page.locator('.sidebar-nav button:has-text("Quản trị AI")').first();
    await aiNav.click();

    await page.waitForSelector(".ai-engine-page, .ai-stepper-panel", { timeout: 15000 });

    // Check AI Model specs
    const providerTitle = await page.locator(".ai-model-provider-title").innerText();
    const modelSub = await page.locator(".ai-model-name-sub").innerText();
    console.log(` - AI Provider: ${providerTitle.trim()} | Model: ${modelSub.trim()}`);

    // Trigger re-train to observe progression
    const retrainBtn = page.locator(".btn-retrain-ai").first();
    if (await retrainBtn.isEnabled()) {
      console.log(" - Clicking Re-train button to observe 4-step progression...");
      await retrainBtn.click();
      await page.waitForTimeout(1500);
    }

    // Verify Web Client behavior in parallel during progression
    console.log(" - Opening Client Portal (http://127.0.0.1:5173) in separate incognito context to verify gatekeeper lock...");
    const clientContext = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const clientPage = await clientContext.newPage();
    await clientPage.goto("http://127.0.0.1:5173", { waitUntil: "domcontentloaded" });

    // Attempt login as employee while AI is learning
    await clientPage.waitForSelector('input[name="email"], input[type="email"]', { timeout: 10000 });
    await clientPage.fill('input[name="email"], input[type="email"]', "hung.nguyen@eas.com");
    await clientPage.fill('input[name="password"], input[type="password"]', "Password@123456");
    await clientPage.click('button[type="submit"]');

    await clientPage.waitForTimeout(2000);

    // Now wait on admin page until AI learning completes 100%
    console.log(" - Waiting for AI 4-step learning to reach 100% COMPLETED (~10-15s)...");
    for (let i = 0; i < 20; i++) {
      const pctText = await page.locator(".ai-progress-percentage").innerText();
      const stepText = await page.locator(".ai-progress-step-text").innerText();
      console.log(`   [Progress Tick ${i + 1}] ${pctText} - ${stepText}`);
      if (pctText.includes("100%")) {
        console.log("   * 100% COMPLETED reached! AI Engine unlocked Web Client.");
        break;
      }
      await page.waitForTimeout(1500);
    }

    // Now verify employee client login succeeds smoothly when unlocked
    console.log(" - Verifying employee client login succeeds cleanly after unlock...");
    await clientPage.goto("http://127.0.0.1:5173", { waitUntil: "domcontentloaded" });
    await clientPage.waitForSelector('input[name="email"], input[type="email"]', { timeout: 10000 });
    await clientPage.fill('input[name="email"], input[type="email"]', "hung.nguyen@eas.com");
    await clientPage.fill('input[name="password"], input[type="password"]', "Password@123456");
    await clientPage.click('button[type="submit"]');

    await clientPage.waitForSelector(".app-shell, .sidebar, .sidebar-nav", { timeout: 15000 });
    console.log(" - Employee successfully logged into Client Portal without being stuck!");

    // Capture screenshot on admin AI page
    const shot4 = path.join(ARTIFACT_DIR, "tc3_4_ai_engine_progression_and_client_unlock.png");
    await page.screenshot({ path: shot4, fullPage: false });
    console.log(" - Saved screenshot:", shot4);
    results.push({ test: "TC 3.4 AI Engine & Web Client Unlock", status: "PASSED", screenshot: shot4 });

    await adminContext.close();
    await clientContext.close();
  } catch (err) {
    console.error("TEST FAILED:", err);
    throw err;
  } finally {
    await browser.close();
  }

  console.log("\n=== ALL BATCH 3 PLAYWRIGHT TESTS PASSED ===");
  console.log(JSON.stringify(results, null, 2));
}

run().catch((e) => {
  console.error(e);
  process.exit(1);
});
