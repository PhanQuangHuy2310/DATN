// Kiểm tra menu ngăn kéo ở màn hình hẹp (lỗi từ video 18/11): nút "‹" không còn hiện, trạng thái thu gọn của màn hình
// lớn không làm méo ngăn kéo, lớp phủ không đổi màu khi rê/bấm và phủ cả thanh trên cùng.
//   node e2e/mobile_drawer_check.mjs [thư-mục-ảnh]   (cần stack Docker local + EAS_LIVE_PASSWORD)
import { chromium } from "@playwright/test";

const OUT = process.argv[2] || ".";
const PASSWORD = process.env.EAS_LIVE_PASSWORD;
const cases = [
  { name: "admin-760", url: "http://127.0.0.1:8081", email: "admin@eas.com", width: 760, height: 820 },
  { name: "admin-390", url: "http://127.0.0.1:8081", email: "admin@eas.com", width: 390, height: 844 },
  { name: "client-390", url: "http://127.0.0.1:8080", email: "khoa.le@eas.com", width: 390, height: 844 },
];
const problems = [];
const browser = await chromium.launch();
for (const c of cases) {
  const page = await browser.newPage({ viewport: { width: c.width, height: c.height } });
  await page.goto(c.url, { waitUntil: "networkidle" });
  // Trạng thái "thu gọn" đã lưu từ màn hình lớn (đúng tình huống trong video).
  await page.evaluate(() => localStorage.setItem("eas.sidebarCollapsed", "1"));
  await page.locator('input[autocomplete="username"]').fill(c.email);
  await page.locator('input[autocomplete="current-password"]').fill(PASSWORD);
  await page.locator('button[type="submit"]').first().click();
  await page.locator(".menu-toggle").waitFor({ state: "visible", timeout: 20000 });
  await page.waitForTimeout(800);
  // Đóng các thông báo hệ thống bật lên sau đăng nhập (vd. "Quy định … bị trả lại").
  for (let i = 0; i < 60; i++) {
    const open = await page.locator("dialog[open]").count();
    if (!open) {
      await page.waitForTimeout(700); // thông báo kế tiếp có thể bật lên sau một nhịp
      if (!(await page.locator("dialog[open]").count())) break;
    }
    if (i === 0) await page.screenshot({ path: `${OUT}/${c.name}-announcement.png` });
    await page.locator("dialog[open] button").last().click();
    await page.waitForTimeout(250);
  }
  await page.locator(".menu-toggle").click();
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${OUT}/${c.name}-open.png` });

  const edgeVisible = await page.locator(".sidebar .sidebar-edge-toggle").isVisible();
  if (edgeVisible) problems.push(`${c.name}: nút ‹ vẫn hiện`);
  const collapsedShell = await page.locator(".app-shell.sidebar-collapsed").count();
  if (collapsedShell) problems.push(`${c.name}: ngăn kéo vẫn ở trạng thái thu gọn`);
  const navTextVisible = await page.locator(".sidebar .nav-item .nav-text").first().isVisible();
  if (!navTextVisible) problems.push(`${c.name}: chữ menu bị ẩn`);

  const backdrop = page.locator("button.nav-backdrop");
  const before = await backdrop.evaluate((el) => getComputedStyle(el).backgroundColor);
  const box = await backdrop.boundingBox();
  await page.mouse.move(box.x + box.width - 20, box.y + box.height / 2);
  await page.mouse.down();
  const during = await backdrop.evaluate((el) => getComputedStyle(el).backgroundColor);
  await page.screenshot({ path: `${OUT}/${c.name}-press.png` });
  if (before !== during) problems.push(`${c.name}: lớp phủ đổi màu khi bấm (${before} -> ${during})`);
  // Lớp phủ phải nằm trên thanh trên cùng: điểm giữa thanh trên cùng (bên phải ngăn kéo) thuộc về lớp phủ.
  const top = await page.locator(".topbar").boundingBox();
  const hit = await page.evaluate(({ x, y }) => document.elementFromPoint(x, y)?.className || "", {
    x: top.x + top.width - 30, y: top.y + top.height / 2,
  });
  if (!String(hit).includes("nav-backdrop")) problems.push(`${c.name}: thanh trên cùng không bị lớp phủ che (${hit})`);
  await page.mouse.up();
  await page.waitForTimeout(400);
  const stillOpen = await page.locator(".sidebar.open").count();
  if (stillOpen) problems.push(`${c.name}: bấm lớp phủ không đóng menu`);
  console.log(`${c.name}: nền lớp phủ ${before}, điểm trên thanh trên cùng thuộc "${hit}"`);
  await page.close();
}
await browser.close();
console.log(problems.length ? `LỖI:\n- ${problems.join("\n- ")}` : "OK: không còn lỗi ngăn kéo/lớp phủ");
process.exit(problems.length ? 1 : 0);
