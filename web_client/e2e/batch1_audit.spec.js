import { test, expect } from "@playwright/test";

const ADMIN_URL = "http://127.0.0.1:8081";
const CLIENT_URL = "http://127.0.0.1:5173";

test.describe("BATCH 1: AUDIT & CROSS-PORTAL LOGIN RESTRICTION", () => {
  test.beforeEach(async ({ context }) => {
    await context.clearCookies();
  });

  test("TC 1.3: Admin Portal (8081) - Employee account must be blocked", async ({ page }) => {
    await page.goto(ADMIN_URL);
    await page.waitForSelector('input[name="email"]', { timeout: 10000 });

    // Try logging in with an employee account
    await page.fill('input[name="email"]', "hung.nguyen@eas.com");
    await page.fill('input[name="password"]', "Password@123456");
    await page.click('button[type="submit"]');

    // Verify error message is visible and matches exactly
    const errorLocator = page.locator('.error, [role="alert"]');
    await expect(errorLocator).toBeVisible({ timeout: 5000 });
    const text = await errorLocator.textContent();
    console.log("TC 1.3 Employee blocked message:", text);
    expect(text).toContain("Tài khoản nhân viên không được phép đăng nhập vào Cổng Quản trị (8081)");

    await page.screenshot({ path: "C:/Users/PHAN QUANG HUY/.gemini/antigravity/brain/f3a0e7bd-8e68-488f-8a6a-9f9afecd4111/tc1_3_admin_portal_employee_blocked.png" });
  });

  test("TC 1.3 & 1.5: Admin Portal (8081) - Admin account admin@eas.com logs in & Sidebar has 9 items", async ({ page }) => {
    await page.goto(ADMIN_URL);
    await page.waitForSelector('input[name="email"]', { timeout: 10000 });

    await page.fill('input[name="email"]', "admin@eas.com");
    await page.fill('input[name="password"]', "admin@123456789");
    await page.click('button[type="submit"]');

    // Wait for workspace to load
    await page.waitForSelector(".sidebar-nav", { timeout: 15000 });
    console.log("TC 1.3 Admin logged in successfully to 8081");

    // TC 1.5: Verify exact 9 sidebar items
    const navItems = page.locator(".sidebar-nav .nav-item .nav-text");
    const count = await navItems.count();
    console.log("TC 1.5 Admin sidebar items count:", count);
    const itemTexts = [];
    for (let i = 0; i < count; i++) {
      itemTexts.push(await navItems.nth(i).textContent());
    }
    console.log("TC 1.5 Admin sidebar items:", itemTexts);
    expect(count).toBe(9);
    expect(itemTexts).toContain("Tổng quan");
    expect(itemTexts).toContain("Yêu cầu & Quy trình");
    expect(itemTexts).toContain("Sơ đồ công ty");
    expect(itemTexts).toContain("Người dùng");
    expect(itemTexts).toContain("Phân quyền");
    expect(itemTexts).toContain("Quy định");
    expect(itemTexts).toContain("Quản trị AI");
    expect(itemTexts).toContain("Quản lý API");
    expect(itemTexts).toContain("Phiên bản hệ thống");

    // Verify Header active page title
    await expect(page.locator(".sidebar-nav")).toBeVisible();

    await page.screenshot({ path: "C:/Users/PHAN QUANG HUY/.gemini/antigravity/brain/f3a0e7bd-8e68-488f-8a6a-9f9afecd4111/tc1_5_admin_portal_sidebar_9_items.png" });
  });

  test("TC 1.4: Client Portal - admin@eas.com must be blocked", async ({ page }) => {
    await page.goto(CLIENT_URL);
    await page.waitForSelector('input[name="email"]', { timeout: 10000 });

    await page.fill('input[name="email"]', "admin@eas.com");
    await page.fill('input[name="password"]', "admin@123456789");
    await page.click('button[type="submit"]');

    // Verify error message is visible and matches exactly
    const errorLocator = page.locator('.error, [role="alert"]');
    await expect(errorLocator).toBeVisible({ timeout: 5000 });
    const text = await errorLocator.textContent();
    console.log("TC 1.4 Admin blocked message on Client Portal:", text);
    expect(text).toContain("Tài khoản Quản trị viên (admin@eas.com) không được phép đăng nhập vào Cổng Nhân viên (8080)");

    await page.screenshot({ path: "C:/Users/PHAN QUANG HUY/.gemini/antigravity/brain/f3a0e7bd-8e68-488f-8a6a-9f9afecd4111/tc1_4_client_portal_admin_blocked.png" });
  });

  test("TC 1.4: Client Portal - Employee hung.nguyen@eas.com logs in successfully", async ({ page }) => {
    await page.goto(CLIENT_URL);
    await page.waitForSelector('input[name="email"]', { timeout: 10000 });

    await page.fill('input[name="email"]', "hung.nguyen@eas.com");
    await page.fill('input[name="password"]', "Password@123456");
    await page.click('button[type="submit"]');

    // Wait for client workspace to load
    await page.waitForSelector(".sidebar-nav", { timeout: 15000 });
    console.log("TC 1.4 Employee logged in successfully to Client Portal");
    await expect(page.locator(".sidebar-nav")).toBeVisible();

    await page.screenshot({ path: "C:/Users/PHAN QUANG HUY/.gemini/antigravity/brain/f3a0e7bd-8e68-488f-8a6a-9f9afecd4111/tc1_4_client_portal_employee_logged_in.png" });
  });
});
