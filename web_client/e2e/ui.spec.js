import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
const id = "11111111-1111-4111-8111-111111111111";
const userId = "22222222-2222-4222-8222-222222222222";
const all = [
  "REQUESTER",
  "APPROVER",
  "EXECUTOR",
  "ACCEPTOR",
  "POLICY_ADMIN",
  "OPS_ADMIN",
  "AUDITOR",
];
const statuses = [
  "DRAFT",
  "PENDING_APPROVAL",
  "NEEDS_INFO",
  "READY_FOR_EXECUTION",
  "IN_PROGRESS",
  "WAITING_FOR_ACCEPTANCE",
  "COMPLETED",
  "REJECTED",
  "CANCELLED",
];
async function fixture(page, role = "REQUESTER", state = "DRAFT") {
  const calls = [];
  let version = 0;
  let status = state;
  const request = () => ({
    id,
    code: "REQ-2026-001",
    type_code: "LEAVE",
    status,
    lock_version: version,
    requester_id: (role === "REQUESTER" || role === "ALL") ? userId : "33333333-3333-4333-8333-333333333333",
    payload: {
      title: "Đăng ký nghỉ phép tháng 10",
      reason: "Nghỉ phép theo kế hoạch cá nhân",
      start_date: "2026-10-25",
      end_date: "2026-10-26",
      handover_user_id: id,
    },
    created_at: "2026-10-23T09:00:00Z",
    updated_at: "2026-10-23T09:00:00Z",
    approval_steps: [
      {
        step_no: 1,
        state: (role === "APPROVER" || role === "ALL") && status === "PENDING_APPROVAL" ? "ACTIVE" : (status === "DRAFT" ? "PENDING" : "APPROVED"),
        assignee_id: (role === "APPROVER" || role === "ALL") ? userId : "44444444-4444-4444-8444-444444444444",
      },
    ],
    workflow: {
      lifecycle: "C",
      acceptor_id: (role === "ACCEPTOR" || role === "ALL") ? userId : "55555555-5555-4555-8555-555555555555",
      attempt: {
        executor_id: (role === "EXECUTOR" || (role === "ALL" && status !== "WAITING_FOR_ACCEPTANCE")) ? userId : "66666666-6666-4666-8666-666666666666",
        state: status === "WAITING_FOR_ACCEPTANCE" ? "SUBMITTED" : (status === "READY_FOR_EXECUTION" ? "READY" : "RUNNING"),
        attempt_no: 1,
      },
    },
  });
  await page.route("**/api/v1/**", async (route) => {
    const req = route.request(),
      url = new URL(req.url()),
      path = url.pathname.replace("/api/v1/", "");
    let body = req.postData();
    try {
      body = JSON.parse(body);
    } catch {}
    calls.push({ path, method: req.method(), body, url });
    const send = (value, code = 200) =>
      route.fulfill({
        status: code,
        contentType: "application/json",
        body: JSON.stringify(value),
      });
    if (path === "auth/csrf") return send({});
    if (path === "auth/me")
      return send({
        user: {
          id: userId,
          display_name: "Nguyễn Minh Anh",
          roles: role === "ALL" ? all : [role],
          capabilities: { identity_manage: role === "OPS_ADMIN" || role === "ALL" },
        },
      });
    if (path === "reports/requests") {
      if (!url.searchParams.get("created_from"))
        return send({ error: { code: "PERIOD_INVALID" } }, 422);
      return send({
        report: {
          period: { from: "2026-09-23", to: "2026-10-23" },
          submitted: 24,
          approved: 18,
          completed: 12,
          completed_rate: 0.5,
          by_status: { PENDING_APPROVAL: 6, COMPLETED: 12 },
        },
      });
    }
    if (path === "requests")
      return send({
        items: statuses
          .filter(
            (s) =>
              !url.searchParams.get("status") ||
              s === url.searchParams.get("status"),
          )
          .map((s, i) => ({
            ...request(),
            id: i === 0 ? id : `r${i}`,
            status: s,
            code: `REQ-2026-00${i + 1}`,
          })),
        next_offset: null,
      });
    if (path === "request-drafts" && req.method() === "POST")
      return send({ request: request() }, 201);
    if (path === `request-drafts/${id}`) {
      expect(body.expected_version).toBe(version);
      version++;
      return send({ request: request() });
    }
    if (path === `requests/${id}`) return send({ request: request() });
    if (path === "requests/submit") {
      expect(body.expected_version).toBe(version);
      status = "PENDING_APPROVAL";
      version++;
      return send({ request: request() });
    }
    if (path.endsWith("/cancel")) {
      expect(body.reason.length).toBeGreaterThanOrEqual(10);
      expect(body.expected_version).toBe(version);
      status = "CANCELLED";
      version++;
      return send({ request: request() });
    }
    if (
      path.endsWith("/approval-decisions") ||
      path.endsWith("/acceptance-decisions") ||
      path.endsWith("/execution/start")
    ) {
      expect(body.expected_version).toBe(version);
      return send({ request: request() });
    }
    if (path.endsWith("/revisions")) return send({ revisions: [] });
    if (path.endsWith("/audit")) return send({ items: [] });
    if (path === "admin-events") return send({ items: [] });
    if (path === "config-releases")
      return send({
        items: [
          {
            id,
            type_code: "LEAVE",
            version: 1,
            state: "DRAFT",
            lock_version: 0,
          },
        ],
      });
    if (path === `config-releases/${id}`)
      return send({
        release: {
          id,
          type_code: "LEAVE",
          version: 1,
          state: "DRAFT",
          lock_version: 0,
          form_schema: {},
          route_rules: {},
          actor_bindings: {},
          sla_profile: {},
        },
      });
    if (path.endsWith("/validate"))
      return send({ valid: true, validation_hash: "abc", lock_version: 0 });
    if (path.endsWith("/publish")) {
      expect(body.validation_hash).toBe("abc");
      return send({});
    }
    if (path === "ops/requests")
      return send({
        items: [
          {
            ...request(),
            status: "IN_PROGRESS",
            current_attempt: { id, executor_id: userId },
            sla: { due_at: "2026-10-25" },
          },
        ],
        next_offset: null,
      });
    if (path.endsWith("/reassign")) return send({});
    if (path === "notifications")
      return send({
        items: [
          {
            id,
            label: "Bạn có yêu cầu mới cần xử lý",
            request_id: id,
            read_at: null,
            created_at: "2026-10-23",
          },
        ],
        next_offset: null,
      });
    if (path.endsWith("/read"))
      return send({ notification: { id, read_at: "2026-10-23" } });
    if (path === "meta/request-type-forms")
      return send({
        items: [
          {
            code: "LEAVE",
            name: "Nghỉ phép",
            lifecycle: "C",
            risk_weight: 1,
            approval_level: 3,
            release_id: id,
            form_schema: {
              type: "object",
              required: ["title", "reason", "start_date", "end_date"],
              properties: {
                title: { type: "string", title: "Tiêu đề" },
                reason: { type: "string", title: "Lý do" },
                start_date: { type: "string", format: "date", title: "Ngày bắt đầu" },
                end_date: { type: "string", format: "date", title: "Ngày kết thúc" },
                handover_user_id: { type: "string", format: "uuid", title: "ID người nhận bàn giao" },
              },
            },
            field_labels: {
              title: "Tiêu đề",
              reason: "Lý do",
              start_date: "Ngày bắt đầu",
              end_date: "Ngày kết thúc",
              handover_user_id: "ID người nhận bàn giao",
            },
          },
        ],
      });
    return send({});
  });
  return calls;
}
for (const role of all) {
  test(`navigation for ${role}`, async ({ page }) => {
    await fixture(page, role);
    await page.goto("/");
    await expect(
      page.getByRole("heading", { name: "Tổng quan xử lý yêu cầu" }),
    ).toBeVisible();
    const nav = page.getByRole("navigation");
    await expect(
      nav.getByRole("button", { name: "Cấu hình quy trình" }),
    ).toHaveCount(role === "POLICY_ADMIN" ? 1 : 0);
    await expect(
      nav.getByRole("button", { name: "Theo dõi vận hành" }),
    ).toHaveCount(role === "OPS_ADMIN" ? 1 : 0);
    await expect(
      nav.getByRole("button", { name: "Chờ tôi phê duyệt" }),
    ).toHaveCount(role === "APPROVER" ? 1 : 0);
  });
}
test("all statuses, filter, draft update and cancellation with reason", async ({
  page,
}) => {
  const calls = await fixture(page);
  await page.goto("/");
  await page.getByRole("navigation").getByText("Yêu cầu của tôi").click();
  await expect(page.getByLabel("Trạng thái").locator("option")).toHaveCount(10);
  await page.getByLabel("Trạng thái").selectOption("CANCELLED");
  await expect(page.getByRole("cell", { name: "Đã hủy" })).toBeVisible();
  await page.getByLabel("Trạng thái").selectOption("");
  await page.getByRole("button", { name: "Xem chi tiết →" }).first().click();
  await page.getByRole("button", { name: "Chỉnh sửa / bổ sung" }).click();
  await page
    .getByLabel("Tiêu đề", { exact: true })
    .fill("Đăng ký nghỉ phép đã cập nhật");
  await page.getByRole("button", { name: "Lưu bản nháp", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Đã lưu");
  await page
    .getByRole("button", { name: "Gửi phê duyệt", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Nội dung đề nghị" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Hủy yêu cầu", exact: true }).click();
  await page.getByLabel("Lý do / nhận xét").fill("Không còn nhu cầu sử dụng");
  await page.getByRole("button", { name: "Xác nhận", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  expect(
    calls.find((c) => c.path.endsWith("/cancel")).body.expected_version,
  ).toBe(3);
});
test("terminal requests cannot be cancelled or edited", async ({ page }) => {
  await fixture(page, "REQUESTER", "COMPLETED");
  await page.goto("/");
  await page.getByRole("navigation").getByText("Yêu cầu của tôi").click();
  await page.getByRole("button", { name: "Xem chi tiết →" }).first().click();
  await expect(
    page.getByRole("heading", { name: "Nội dung đề nghị" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Hủy yêu cầu", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Chỉnh sửa / bổ sung" }),
  ).toHaveCount(0);
});
test("approval rejects with reason and correct command", async ({ page }) => {
  const calls = await fixture(page, "APPROVER", "PENDING_APPROVAL");
  await page.goto("/");
  await page.getByRole("navigation").getByText("Chờ tôi phê duyệt").click();
  await page.getByRole("button", { name: "Xem chi tiết →" }).first().click();
  await page.getByRole("button", { name: "Từ chối", exact: true }).click();
  await page
    .getByLabel("Lý do / nhận xét")
    .fill("Thông tin chưa đáp ứng yêu cầu");
  await page.getByRole("button", { name: "Xác nhận", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  expect(
    calls.find((c) => c.path.endsWith("/approval-decisions")).body.outcome,
  ).toBe("REJECT");
});
test("policy validate before publish", async ({ page }) => {
  await fixture(page, "POLICY_ADMIN");
  await page.goto("/");
  await page.getByRole("navigation").getByText("Cấu hình quy trình").click();
  await page.getByRole("button", { name: "Mở cấu hình" }).click();
  await expect(
    page.getByRole("button", { name: "Công bố phiên bản", exact: true }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Kiểm tra cấu hình" }).click();
  await page
    .getByRole("button", { name: "Công bố phiên bản", exact: true })
    .click();
  await page
    .getByLabel("Lý do / nhận xét")
    .fill("Công bố cấu hình đã kiểm tra");
  await page.getByRole("button", { name: "Xác nhận", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
});
test("notifications mark read and mobile layout", async ({ page }) => {
  const calls = await fixture(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.getByRole("button", { name: "Mở điều hướng" }).click();
  await page.getByRole("navigation").getByText("Thông báo").click();
  await page.getByRole("button", { name: "Đánh dấu đã đọc" }).click();
  await expect
    .poll(() => calls.some((c) => c.path.endsWith("/read")))
    .toBeTruthy();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
});
test("desktop visual and accessibility", async ({ page }) => {
  await fixture(page, "ALL");
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Tổng quan xử lý yêu cầu" }),
  ).toBeVisible();
  await page.screenshot({ path: "test-results/dashboard.png", fullPage: true });
  await page.getByRole("navigation").getByText("Yêu cầu của tôi").click();
  await expect(page.getByRole("cell", { name: "Đã hủy" })).toBeVisible();
  await page.screenshot({ path: "test-results/requests.png", fullPage: true });
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  expect(results.violations).toEqual([]);
});

test("executor claims only assigned work", async ({ page }) => {
  const calls = await fixture(page, "EXECUTOR", "READY_FOR_EXECUTION");
  await page.goto("/");
  await page.getByRole("navigation").getByText("Công việc thực hiện").click();
  await page.getByRole("button", { name: "Xem chi tiết →" }).first().click();
  await page
    .getByRole("button", { name: "Nhận công việc", exact: true })
    .click();
  await page.getByRole("button", { name: "Xác nhận", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  expect(calls.some((c) => c.path.endsWith("/execution/start"))).toBeTruthy();
});
test("acceptor requests rework with reason", async ({ page }) => {
  const calls = await fixture(page, "ACCEPTOR", "WAITING_FOR_ACCEPTANCE");
  await page.goto("/");
  await page.getByRole("navigation").getByText("Chờ nghiệm thu").click();
  await page.getByRole("button", { name: "Xem chi tiết →" }).first().click();
  await page
    .getByRole("button", { name: "Yêu cầu làm lại", exact: true })
    .click();
  await page
    .getByLabel("Lý do / nhận xét")
    .fill("Kết quả cần bổ sung minh chứng");
  await page.getByRole("button", { name: "Xác nhận", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  expect(
    calls.find((c) => c.path.endsWith("/acceptance-decisions")).body.outcome,
  ).toBe("REWORK");
});
test("ops reassign posts selected target and version", async ({ page }) => {
  const calls = await fixture(page, "OPS_ADMIN");
  await page.goto("/");
  await page.getByRole("navigation").getByText("Theo dõi vận hành").click();
  await page.getByRole("button", { name: "Điều chuyển", exact: true }).click();
  await page.getByLabel("ID người nhận mới").fill(userId);
  await page
    .getByRole("dialog")
    .getByLabel("Lý do / nhận xét")
    .fill("Điều chuyển do người cũ vắng mặt");
  await page.getByRole("button", { name: "Xác nhận", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  const body = calls.find((c) => c.path.endsWith("/reassign")).body;
  expect(body.target_kind).toBe("EXECUTOR");
  expect(body.target_id).toBe(id);
  expect(body.expected_version).toBe(0);
});

test('identity CRUD creates, edits and deactivates department',async({page})=>{
 const calls=[];await fixture(page,'OPS_ADMIN');let list=[];
 await page.route('**/api/v1/admin/**',async route=>{const req=route.request(),url=new URL(req.url());let body=req.postDataJSON();calls.push({method:req.method(),body});
 if(req.method()==='POST'){list=[{id,code:body.code,name:body.name,parent_id:null,is_active:true,revision:'r1'}];}
 if(req.method()==='PATCH'){expect(body.expected_revision).toBe('r1');list=[{...list[0],name:body.name,revision:'r2'}];}
 if(req.method()==='DELETE'){expect(body.expected_revision).toBe('r2');list=[{...list[0],is_active:false,revision:'r3'}];}
 await route.fulfill({json:req.method()==='GET'?{items:url.pathname.endsWith('/departments')?list:[],next_offset:null}:{item:list[0]}});
 });
 await page.goto('/');await page.getByRole('navigation').getByText('Danh tính & phân quyền').click();await page.getByRole('button',{name:'Phòng ban',exact:true}).click();await page.getByRole('button',{name:'+ Thêm mới'}).click();await page.getByLabel('Mã phòng ban').fill('DEV');await page.getByLabel('Tên phòng ban').fill('Phòng phát triển');await page.getByRole('dialog').getByLabel('Lý do / nhận xét').fill('Thêm phòng ban phục vụ kiểm thử');await page.getByRole('button',{name:'Xác nhận',exact:true}).click();await expect(page.getByRole('dialog')).toHaveCount(0);await expect(page.getByRole('cell').filter({hasText:'Phòng phát triển'})).toBeVisible();await page.getByRole('button',{name:'Sửa',exact:true}).click();await page.getByLabel('Tên phòng ban').fill('Phòng kỹ thuật');await page.getByRole('dialog').getByLabel('Lý do / nhận xét').fill('Cập nhật tên phòng ban kiểm thử');await page.getByRole('button',{name:'Xác nhận',exact:true}).click();await expect(page.getByRole('dialog')).toHaveCount(0);await page.getByRole('button',{name:'Vô hiệu hóa',exact:true}).click();await page.getByRole('dialog').getByLabel('Lý do / nhận xét').fill('Ngừng sử dụng phòng ban kiểm thử');await page.getByRole('button',{name:'Xác nhận',exact:true}).click();await expect(page.getByRole('cell',{name:'Ngừng hoạt động',exact:true})).toBeVisible();expect(calls.filter(c=>c.method!=='GET').map(c=>c.method)).toEqual(['POST','PATCH','DELETE']);
});
test('temporary password blocks workspace until changed',async({page})=>{
 await fixture(page);let changed=false;
 await page.route('**/api/v1/auth/me',route=>route.fulfill(changed?{json:{user:{id:userId,display_name:'Test User',roles:['REQUESTER'],must_change_password:false}}}:{status:403,json:{error:{code:'PASSWORD_CHANGE_REQUIRED'}}}));
 await page.route('**/api/v1/auth/password',async route=>{const body=route.request().postDataJSON();expect(body.current_password).toBe('Old!12345678');expect(body.new_password).toBe('New!87654321Pass');changed=true;await route.fulfill({json:{status:'ok'}});});
 await page.goto('/');await expect(page.getByRole('heading',{name:'Đổi mật khẩu để tiếp tục'})).toBeVisible();await expect(page.getByRole('navigation')).toHaveCount(0);await page.getByLabel('Mật khẩu hiện tại').fill('Old!12345678');await page.getByLabel('Mật khẩu mới',{exact:true}).fill('New!87654321Pass');await page.getByLabel('Xác nhận mật khẩu').fill('New!87654321Pass');await page.getByRole('button',{name:'Đổi mật khẩu',exact:true}).click();await expect(page.getByRole('heading',{name:'Tổng quan xử lý yêu cầu'})).toBeVisible();
});
