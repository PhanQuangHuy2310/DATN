import test from "node:test";
import assert from "node:assert/strict";
import { delegationActive, delegationBody } from "../src/delegation.js";

test("delegation form values become an ISO window", () => {
  const body = delegationBody({ delegate_id: "d1", starts_at: "2026-11-03T08:00", ends_at: "2026-11-10T17:00", reason: " Nghỉ phép năm " });
  assert.equal(body.delegate_id, "d1");
  assert.equal(body.reason, "Nghỉ phép năm");
  assert.ok(body.starts_at.endsWith("Z") && body.ends_at > body.starts_at);
});

test("end must be after start", () => {
  assert.throws(() => delegationBody({ delegate_id: "d", starts_at: "2026-11-10T08:00", ends_at: "2026-11-03T08:00", reason: "Nghỉ" }), /kết thúc/);
  assert.throws(() => delegationBody({ delegate_id: "d", starts_at: "", ends_at: "2026-11-03T08:00", reason: "Nghỉ" }), /không hợp lệ/);
});

test("active only inside the window and when not revoked", () => {
  const item = { starts_at: "2026-11-03T00:00:00Z", ends_at: "2026-11-10T00:00:00Z", revoked_at: null };
  assert.equal(delegationActive(item, Date.parse("2026-11-05T00:00:00Z")), true);
  assert.equal(delegationActive(item, Date.parse("2026-11-11T00:00:00Z")), false);
  assert.equal(delegationActive({ ...item, revoked_at: "2026-11-04T00:00:00Z" }, Date.parse("2026-11-05T00:00:00Z")), false);
});
