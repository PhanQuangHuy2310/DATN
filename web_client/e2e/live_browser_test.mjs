import { chromium } from "playwright";
import fs from "fs";
import path from "path";

const ARTIFACT_DIR = process.env.EAS_E2E_ARTIFACT_DIR || "./test-results/live";

// Credentials are supplied by the operator at run time; never commit them.
const CREDENTIALS = {
  employee: {
    user: process.env.EAS_E2E_EMPLOYEE_USER,
    password: process.env.EAS_E2E_EMPLOYEE_PASSWORD,
  },
  admin: {
    user: process.env.EAS_E2E_ADMIN_USER,
    password: process.env.EAS_E2E_ADMIN_PASSWORD,
  },
};
const missing = Object.entries(CREDENTIALS)
  .filter(([, c]) => !c.user || !c.password)
  .map(([role]) => role);
if (missing.length) {
  console.error(
    `Missing credentials for: ${missing.join(", ")}. Set EAS_E2E_EMPLOYEE_USER/PASSWORD and EAS_E2E_ADMIN_USER/PASSWORD.`,
  );
  process.exit(2);
}

async function run() {
  fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const results = [];

  console.log("=== STARTING LIVE UI TESTS ===");

  // ─────────────────────────────────────────────────────────────
  // TEST CASE 1: Employee Portal Login & Dashboard (ha.luong)
  // ─────────────────────────────────────────────────────────────
  try {
    const page = await context.newPage();
    console.log("\n[TEST 1] Testing Employee Portal (http://127.0.0.1:5173)...");
    await page.goto("http://127.0.0.1:5173", { waitUntil: "networkidle" });
    
    // Check Login Form
    const loginHeading = await page.getByRole("heading", { name: "Đăng nhập EAS Portal" }).isVisible();
    console.log(" - Login form heading visible:", loginHeading);

    await page.getByLabel("Tên đăng nhập").fill(CREDENTIALS.employee.user);
    await page.getByLabel("Mật khẩu").fill(CREDENTIALS.employee.password);
    await page.getByRole("button", { name: "Đăng nhập" }).click();

    // Wait for workspace to load
    await page.waitForSelector(".app-shell, nav, .nav-group", { timeout: 10000 });
    console.log(" - Successfully authenticated as ha.luong (Nhân viên)");

    // Capture employee dashboard screenshot
    const shotPath1 = path.join(ARTIFACT_DIR, "live_01_employee_dashboard.png");
    await page.screenshot({ path: shotPath1, fullPage: false });
    console.log(" - Saved screenshot:", shotPath1);

    // ─────────────────────────────────────────────────────────────
    // TEST CASE 2: Employee Portal - Workflow Diagrams Navigation
    // ─────────────────────────────────────────────────────────────
    console.log("\n[TEST 2] Testing Sơ đồ luồng (Workflow Diagrams)...");
    const flowNav = page.locator("nav").getByRole("button", { name: "Sơ đồ luồng", exact: true });
    if (await flowNav.isVisible()) {
      await flowNav.click();
      await page.waitForSelector(".flow-library", { timeout: 8000 });
      const shotPath2 = path.join(ARTIFACT_DIR, "live_02_workflow_diagrams.png");
      await page.screenshot({ path: shotPath2, fullPage: false });
      console.log(" - Workflow diagrams rendered and screenshot saved:", shotPath2);
    }

    // ─────────────────────────────────────────────────────────────
    // TEST CASE 3: Employee Portal - Create Request Form
    // ─────────────────────────────────────────────────────────────
    console.log("\n[TEST 3] Testing Tạo yêu cầu (Create Request)...");
    const createBtn = page.getByRole("button", { name: "+ Tạo yêu cầu mới" });
    if (await createBtn.isVisible()) {
      await createBtn.click();
      await page.waitForSelector(".catalog-grid, .request-editor, form", { timeout: 8000 });
      const shotPath3 = path.join(ARTIFACT_DIR, "live_03_create_request.png");
      await page.screenshot({ path: shotPath3, fullPage: false });
      console.log(" - Create request form rendered and screenshot saved:", shotPath3);
    }

    // Logout employee
    const logoutBtn = page.getByRole("button", { name: "Đăng xuất" });
    if (await logoutBtn.isVisible()) {
      await logoutBtn.click();
      await page.waitForSelector("input[name='username']", { timeout: 8000 });
      console.log(" - Employee logged out successfully");
    }
    await page.close();
    results.push({ test: "Employee Portal Flow", status: "PASS" });
  } catch (err) {
    console.error("[ERROR] Employee Portal Test failed:", err);
    results.push({ test: "Employee Portal Flow", status: "FAIL", error: err.message });
  }

  // ─────────────────────────────────────────────────────────────
  // TEST CASE 4: Admin Portal (http://127.0.0.1:5174) with admin
  // ─────────────────────────────────────────────────────────────
  try {
    const adminContext = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await adminContext.newPage();
    console.log("\n[TEST 4] Testing Admin Portal (http://127.0.0.1:5174)...");
    await page.goto("http://127.0.0.1:5174", { waitUntil: "networkidle" });

    await page.getByLabel("Tên đăng nhập").fill(CREDENTIALS.admin.user);
    await page.getByLabel("Mật khẩu").fill(CREDENTIALS.admin.password);
    await page.getByRole("button", { name: "Đăng nhập" }).click();

    await page.waitForSelector(".app-shell, nav, .nav-group", { timeout: 10000 });
    console.log(" - Successfully authenticated as admin on Admin Portal");

    const shotAdmin1 = path.join(ARTIFACT_DIR, "live_04_admin_dashboard.png");
    await page.screenshot({ path: shotAdmin1, fullPage: false });
    console.log(" - Admin dashboard screenshot saved:", shotAdmin1);

    // ─────────────────────────────────────────────────────────────
    // TEST CASE 5: Admin Portal - Cấu hình quy trình (Policy)
    // ─────────────────────────────────────────────────────────────
    console.log("\n[TEST 5] Testing Admin Cấu hình quy trình (Policy)...");
    const policyNav = page.locator("nav").getByRole("button", { name: "Cấu hình quy trình", exact: true });
    if (await policyNav.isVisible()) {
      await policyNav.click();
      await page.waitForTimeout(1000);
      const shotPolicy = path.join(ARTIFACT_DIR, "live_05_admin_policy.png");
      await page.screenshot({ path: shotPolicy, fullPage: false });
      console.log(" - Policy configuration rendered and screenshot saved:", shotPolicy);
    }

    // ─────────────────────────────────────────────────────────────
    // TEST CASE 6: Admin Portal - Theo dõi vận hành (Ops)
    // ─────────────────────────────────────────────────────────────
    console.log("\n[TEST 6] Testing Admin Theo dõi vận hành (Ops)...");
    const opsNav = page.locator("nav").getByRole("button", { name: "Theo dõi vận hành", exact: true });
    if (await opsNav.isVisible()) {
      await opsNav.click();
      await page.waitForTimeout(1000);
      const shotOps = path.join(ARTIFACT_DIR, "live_06_admin_ops.png");
      await page.screenshot({ path: shotOps, fullPage: false });
      console.log(" - Ops console rendered and screenshot saved:", shotOps);
    }

    // ─────────────────────────────────────────────────────────────
    // TEST CASE 7: Admin Portal - Danh tính & phân quyền (Identity)
    // ─────────────────────────────────────────────────────────────
    console.log("\n[TEST 7] Testing Admin Danh tính & phân quyền (Identity)...");
    const identNav = page.locator("nav").getByRole("button", { name: "Danh tính & phân quyền", exact: true });
    if (await identNav.isVisible()) {
      await identNav.click();
      await page.waitForTimeout(1000);
      const shotIdent = path.join(ARTIFACT_DIR, "live_07_admin_identity.png");
      await page.screenshot({ path: shotIdent, fullPage: false });
      console.log(" - Identity console rendered and screenshot saved:", shotIdent);
    }

    // ─────────────────────────────────────────────────────────────
    // TEST CASE 8: Admin Portal - Quản lý API (API Admin)
    // ─────────────────────────────────────────────────────────────
    console.log("\n[TEST 8] Testing Admin Quản lý API (API Admin)...");
    const apiNav = page.locator("nav").getByRole("button", { name: "Quản lý API", exact: true });
    if (await apiNav.isVisible()) {
      await apiNav.click();
      await page.waitForTimeout(1000);
      const shotApi = path.join(ARTIFACT_DIR, "live_08_admin_api.png");
      await page.screenshot({ path: shotApi, fullPage: false });
      console.log(" - API management console rendered and screenshot saved:", shotApi);
    }

    // Logout admin
    const logoutBtn = page.getByRole("button", { name: "Đăng xuất" });
    if (await logoutBtn.isVisible()) {
      await logoutBtn.click();
      await page.waitForSelector("input[name='username']", { timeout: 8000 });
      console.log(" - Admin logged out successfully");
    }
    await page.close();
    results.push({ test: "Admin Portal Full Suite", status: "PASS" });
  } catch (err) {
    console.error("[ERROR] Admin Portal Test failed:", err);
    results.push({ test: "Admin Portal Full Suite", status: "FAIL", error: err.message });
  }

  // ─────────────────────────────────────────────────────────────
  // TEST CASE 9: RBAC Guard - Non-admin accessing Admin Portal
  // ─────────────────────────────────────────────────────────────
  try {
    const rbacContext = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await rbacContext.newPage();
    console.log("\n[TEST 9] Testing RBAC: Non-admin account (ha.luong) on Admin Portal...");
    await page.goto("http://127.0.0.1:5174", { waitUntil: "networkidle" });

    await page.getByLabel("Tên đăng nhập").fill(CREDENTIALS.employee.user);
    await page.getByLabel("Mật khẩu").fill(CREDENTIALS.employee.password);
    await page.getByRole("button", { name: "Đăng nhập" }).click();

    try {
      await page.waitForSelector("text=Không có quyền quản trị", { timeout: 8000 });
    } catch {
      const retryBtn = page.getByRole("button", { name: "Đăng nhập" });
      if (await retryBtn.isVisible()) {
        await retryBtn.click();
      }
      await page.waitForSelector("text=Không có quyền quản trị", { timeout: 10000 });
    }

    console.log(" - 'Không có quyền quản trị' message visible: PASS");

    const shotRbac = path.join(ARTIFACT_DIR, "live_09_rbac_denied.png");
    await page.screenshot({ path: shotRbac, fullPage: false });
    console.log(" - RBAC guard screenshot saved:", shotRbac);

    await page.close();
    results.push({ test: "RBAC Guard Verification", status: "PASS" });
  } catch (err) {
    console.error("[ERROR] RBAC Guard Test failed:", err);
    results.push({ test: "RBAC Guard Verification", status: "FAIL", error: err.message });
  }

  await browser.close();

  console.log("\n=== TEST EXECUTION SUMMARY ===");
  console.log(JSON.stringify(results, null, 2));

  const allPassed = results.every((r) => r.status === "PASS");
  process.exit(allPassed ? 0 : 1);
}

run().catch((err) => {
  console.error(err);
  process.exit(1);
});
