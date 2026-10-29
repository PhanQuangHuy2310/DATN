import { test } from "node:test";
import assert from "node:assert/strict";
import { requestActionPayload } from "../src/actionPayload.js";

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
