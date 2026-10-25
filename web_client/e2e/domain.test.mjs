import test from "node:test";
import assert from "node:assert/strict";
import { permissions, statuses } from "../src/domain.js";
const u = {
  id: "me",
  roles: ["REQUESTER", "APPROVER", "EXECUTOR", "ACCEPTOR"],
};
const r = {
  requester_id: "me",
  approval_steps: [{ state: "ACTIVE", assignee_id: "me" }],
  workflow: { acceptor_id: "me", attempt: { executor_id: "me" } },
};
test("terminal states allow no mutations", () => {
  for (const status of ["COMPLETED", "CANCELLED", "REJECTED"])
    assert.ok(Object.values(permissions(u, { ...r, status })).every((v) => !v));
});
test("cancel is limited to owner before execution", () => {
  for (const status of Object.keys(statuses))
    assert.equal(
      permissions(u, { ...r, status }).cancel,
      ["DRAFT", "NEEDS_INFO", "PENDING_APPROVAL"].includes(status),
    );
  assert.equal(
    permissions({ ...u, id: "other" }, { ...r, status: "DRAFT" }).cancel,
    false,
  );
});
test("role alone cannot approve or execute another assignment", () => {
  const other = { ...u, id: "other" };
  assert.equal(
    permissions(other, { ...r, status: "PENDING_APPROVAL" }).approve,
    false,
  );
  assert.equal(
    permissions(other, { ...r, status: "READY_FOR_EXECUTION" }).claim,
    false,
  );
  assert.equal(
    permissions(other, { ...r, status: "WAITING_FOR_ACCEPTANCE" }).accept,
    false,
  );
});
test("claim, execute and accept occur in separate phases", () => {
  assert.equal(
    permissions(u, { ...r, status: "READY_FOR_EXECUTION" }).claim,
    true,
  );
  assert.equal(permissions(u, { ...r, status: "IN_PROGRESS" }).execute, true);
  assert.equal(
    permissions(u, { ...r, status: "WAITING_FOR_ACCEPTANCE" }).accept,
    true,
  );
  assert.equal(permissions(u, { ...r, status: "IN_PROGRESS" }).accept, false);
});
test("revoked role cannot mutate own request", () => {
  assert.equal(
    permissions({ id: "me", roles: [] }, { ...r, status: "DRAFT" }).edit,
    false,
  );
});
