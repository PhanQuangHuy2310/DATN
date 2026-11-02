import { test } from "node:test";
import assert from "node:assert/strict";
import { delegationActive, delegationBody, parsePolicyFile, requestActionPayload } from "../src/actionPayload.js";

test("approve always supplies nullable reason for strict Django validator", () => {
  assert.deepEqual(requestActionPayload("approve", 6), {
    expected_version: 6, outcome: "APPROVE", reason: null,
  });
});
test("accept always supplies nullable reason for strict Django validator", () => {
  assert.deepEqual(requestActionPayload("accept", 7), {
    expected_version: 7, outcome: "ACCEPT", reason: null,
  });
});
test("rejection and additional-info carry mandatory reason", () => {
  for (const [action, outcome] of [["reject", "REJECT"], ["info", "NEEDS_INFO"], ["rework", "REWORK"]]) {
    assert.deepEqual(requestActionPayload(action, 4, { reason: "Cần chứng từ hợp lệ." }), {
      expected_version: 4, outcome, reason: "Cần chứng từ hợp lệ.",
    });
  }
});
test("other commands keep the exact backend body contract", () => {
  assert.deepEqual(requestActionPayload("claim", 4, {ignored: true}), {expected_version: 4});
  assert.deepEqual(requestActionPayload("cancel", 4, {reason: "Không còn nhu cầu."}), {
    expected_version: 4, reason: "Không còn nhu cầu.",
  });
  assert.deepEqual(requestActionPayload("issue", 4, {kind: "BLOCKED", reason: "Tài liệu thiếu."}), {
    expected_version: 4, kind: "BLOCKED", reason: "Tài liệu thiếu.",
  });
});
test("unrecognized action and missing expected_version fail closed", () => {
  assert.throws(() => requestActionPayload("publish", 1), /Unsupported/);
  assert.throws(() => requestActionPayload("approve", null), /expected_version/);
});
test("approve may hand the work down to a chosen executor", () => {
  assert.deepEqual(requestActionPayload("approve", 6, { executor_id: "e1" }), {
    expected_version: 6, outcome: "APPROVE", reason: null, executor_id: "e1",
  });
  assert.deepEqual(requestActionPayload("approve", 6, { executor_id: "" }), {
    expected_version: 6, outcome: "APPROVE", reason: null,
  });
});
test("revoking an AI approval carries the mandatory reason", () => {
  assert.deepEqual(requestActionPayload("revokeAi", 9, { reason: "AI duyệt sai quy định." }), {
    expected_version: 9, reason: "AI duyệt sai quy định.",
  });
});
test("delegation form values become an ISO window", () => {
  const body = delegationBody({ delegate_id: "d1", starts_at: "2026-11-03T08:00", ends_at: "2026-11-10T17:00", reason: " Nghỉ phép năm " });
  assert.equal(body.delegate_id, "d1");
  assert.equal(body.reason, "Nghỉ phép năm");
  assert.ok(body.starts_at.endsWith("Z") && body.ends_at > body.starts_at);
});
test("delegation end must be after start", () => {
  assert.throws(() => delegationBody({ delegate_id: "d", starts_at: "2026-11-10T08:00", ends_at: "2026-11-03T08:00", reason: "Nghỉ" }), /kết thúc/);
  assert.throws(() => delegationBody({ delegate_id: "d", starts_at: "", ends_at: "2026-11-03T08:00", reason: "Nghỉ" }), /không hợp lệ/);
});
test("delegation is active only inside the window and when not revoked", () => {
  const item = { starts_at: "2026-11-03T00:00:00Z", ends_at: "2026-11-10T00:00:00Z", revoked_at: null };
  assert.equal(delegationActive(item, Date.parse("2026-11-05T00:00:00Z")), true);
  assert.equal(delegationActive(item, Date.parse("2026-11-11T00:00:00Z")), false);
  assert.equal(delegationActive({ ...item, revoked_at: "2026-11-04T00:00:00Z" }, Date.parse("2026-11-05T00:00:00Z")), false);
});
test("policy file is parsed into the API body", () => {
  const text = JSON.stringify({ version: "QD-1", rules: [{ id: "r", auto_approve: false }] });
  assert.deepEqual(parsePolicyFile(text), { version: "QD-1", rules: [{ id: "r", auto_approve: false }] });
  assert.equal(parsePolicyFile(text, " QD-2 ").version, "QD-2");
  assert.deepEqual(parsePolicyFile("[]", "QD-3"), { version: "QD-3", rules: [] });
});
test("invalid policy files are rejected with a readable message", () => {
  assert.throws(() => parsePolicyFile("{not json"), /JSON/);
  assert.throws(() => parsePolicyFile(JSON.stringify({ version: "v" })), /rules/);
  assert.throws(() => parsePolicyFile(JSON.stringify({ rules: [] })), /version/);
});
