import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  formatIsoDateOnly,
  formatThousandDots,
  formatVnd,
  isCurrencyField,
  isUuid,
  parseDigits,
  vndToVietnameseWords,
} from "../src/formatters.js";
import { errorText, resolveFieldLabel, types } from "../src/domain.js";

const read = (relPath) => readFileSync(new URL(relPath, import.meta.url), "utf8");

test("currency formatters render thousand dots, VND suffix, and Vietnamese financial words", () => {
  assert.equal(parseDigits("15.000.000 đ"), "15000000");
  assert.equal(formatThousandDots("15000000"), "15.000.000");
  assert.equal(formatVnd(15000000), "15.000.000 ₫");
  assert.equal(vndToVietnameseWords(0), "Không đồng");
  assert.equal(vndToVietnameseWords(15000000), "Mười lăm triệu đồng");
  assert.equal(vndToVietnameseWords(1250000), "Một triệu hai trăm năm mươi nghìn đồng");
  assert.equal(vndToVietnameseWords(105000), "Một trăm lẻ năm nghìn đồng");
  assert.ok(isCurrencyField("estimated_cost"));
  assert.ok(isCurrencyField("total_amount"));
  assert.ok(isCurrencyField("amount_vnd"));
  assert.equal(isCurrencyField("days_count"), false);
});

test("UUID and ISO date helpers detect technical tokens accurately", () => {
  assert.ok(isUuid("11111111-1111-4111-8111-111111111111"));
  assert.equal(isUuid("REQ-2026-0012"), false);
  assert.equal(formatIsoDateOnly("2026-11-05"), "05/11/2026");
  assert.equal(formatIsoDateOnly("not-a-date"), null);
});

test("errorText translates backend codes and validation fields without JSON dumps or 4xx correlation UUIDs", () => {
  const validationErr = Object.assign(new Error("VALIDATION_FAILED"), {
    code: "VALIDATION_FAILED",
    status: 422,
    correlationId: "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
    fields: {
      end_date: ["Ngày kết thúc phải sau ngày bắt đầu"],
      estimated_cost: "REQUIRED",
    },
  });
  const msg = errorText(validationErr);
  assert.ok(!msg.includes("{") && !msg.includes("}"), `Expected no JSON braces in: ${msg}`);
  assert.ok(!msg.includes("aaaaaaaa-bbbb"), `Expected no 4xx correlation UUID in: ${msg}`);
  assert.match(msg, /Ngày kết thúc/);
  assert.match(msg, /Chi phí dự kiến \(VND\)/);

  const leaveErr = Object.assign(new Error("LEAVE_BALANCE_EXCEEDED"), {
    code: "LEAVE_BALANCE_EXCEEDED",
    status: 409,
    correlationId: "11111111-2222-4333-8444-555555555555",
  });
  assert.match(errorText(leaveErr), /Số ngày đăng ký vượt quá quỹ ngày phép còn lại/);
  assert.ok(!errorText(leaveErr).includes("11111111-2222"));

  const serverErr = Object.assign(new Error("INTERNAL_ERROR"), {
    code: "INTERNAL_ERROR",
    status: 500,
    correlationId: "99999999-8888-4777-8666-555555555555",
  });
  assert.match(errorText(serverErr), /Mã hỗ trợ kỹ thuật: 99999999/);
});

test("domain dictionary covers Schema v2 types and friendly Vietnamese field labels", () => {
  assert.equal(types.VEHICLE_BOOKING, "Mượn xe công vụ");
  assert.equal(resolveFieldLabel("handover_user_id"), "Người nhận bàn giao công việc");
  assert.equal(resolveFieldLabel("leave_type"), "Loại nghỉ phép");
});

test("web_client UI/UX audit contracts hold across components", () => {
  const app = read("../src/App.jsx");
  const profile = read("../src/components/ProfilePage.jsx");
  const detail = read("../src/components/RequestDetail.jsx");
  const editor = read("../src/components/RequestEditor.jsx");
  const delegation = read("../src/components/DelegationSettings.jsx");
  const clientRequests = read("../src/components/ClientRequests.jsx");

  // 1. App.jsx is decoupled from Admin.jsx so client bundle stays clean
  assert.ok(!app.includes('./components/Admin.jsx'), "App.jsx must not import Admin.jsx");
  assert.match(app, /NotificationsPage\.jsx/);
  assert.match(app, /ProfilePage\.jsx/);

  // 2. ProfilePage never leaks raw department_id UUID
  assert.ok(!profile.includes("user.department_id"), "ProfilePage must not display user.department_id");
  assert.match(profile, /user\.department_name/);
  assert.match(profile, /ds-pwd-checklist/);

  // 3. RequestDetail never dumps JSON.stringify and restricts hash check to AUDITOR
  assert.ok(!detail.includes("JSON.stringify(rev.payload"), "RequestDetail must not JSON.stringify revision payloads");
  assert.match(detail, /user(\?)?\.roles(\?)?\.includes\("AUDITOR"\)/);
  assert.match(detail, /DANGER_WARNINGS/);

  // 4. RequestEditor provides live CurrencyInput and filters ACCESS roles by app
  assert.match(editor, /function CurrencyInput/);
  assert.match(editor, /vndToVietnameseWords/);
  assert.match(editor, /selectedAppCode/);

  // 5. DelegationSettings confirms before revoking
  assert.match(delegation, /<ConfirmDialog/);
  assert.match(delegation, /danger/);

  // 6. ClientRequests surfaces title, VND amount, sender, and department filter
  assert.match(clientRequests, /department_id/);
  assert.match(clientRequests, /amount_vnd/);
  assert.match(clientRequests, /requester_name/);
});
