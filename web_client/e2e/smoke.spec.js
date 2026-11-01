import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("login screen is keyboard-addressable and has no serious accessibility findings", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveTitle(/EAS|Enterprise Approval System/i);
  await expect(page.getByRole("heading", { name: "Đăng nhập" })).toBeVisible();
  await expect(page.getByLabel("Email nhân viên")).toBeEditable();
  await expect(page.getByLabel("Mật khẩu")).toHaveAttribute("type", "password");

  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Bỏ qua đến nội dung chính" })).toBeFocused();

  const findings = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(findings.violations).toEqual([]);
});

test("invalid credentials fail generically without leaking account state", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Email nhân viên").fill("account-that-does-not-exist@eas.com");
  await page.getByLabel("Mật khẩu").fill("wrong-password");
  await page.getByRole("button", { name: "Đăng nhập" }).click();
  await expect(page.getByRole("alert")).toHaveText("Thông tin đăng nhập không hợp lệ.");
  await expect(page.getByRole("alert")).not.toContainText(/email|password|database|sql/i);
});

test("reverse proxy exposes API readiness without disclosing secrets", async ({ request }) => {
  const response = await request.get("/health/ready");
  expect(response.status()).toBe(200);
  const body = await response.json();
  expect(body.status).toBe("ready");
  expect(JSON.stringify(body)).not.toMatch(/password|secret|token|sb_secret/i);
});

test("authenticated requester can reach dashboard and mock catalog", async ({ page }) => {
  const email = process.env.EAS_E2E_EMAIL;
  const password = process.env.EAS_E2E_PASSWORD;
  test.skip(!email || !password, "Live credentials are intentionally supplied only by the fixture runner.");

  await page.goto("/");
  await page.getByLabel("Email nhân viên").fill(email);
  await page.getByLabel("Mật khẩu").fill(password);
  await page.getByRole("button", { name: "Đăng nhập" }).click();
  await expect(page.getByText("DEMO REQUESTER", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Tạo yêu cầu" })).toBeVisible();

  const catalog = await page.request.get("/api/v1/mock/assets/items");
  expect(catalog.status()).toBe(200);
  const catalogBody = await catalog.json();
  expect(Array.isArray(catalogBody.data?.items)).toBeTruthy();
  expect(catalogBody.data.items.length).toBeGreaterThan(0);

  const findings = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(findings.violations).toEqual([]);

  await page.getByRole("button", { name: "Đăng xuất" }).click();
  await expect(page.getByRole("heading", { name: "Đăng nhập" })).toBeVisible();
});
