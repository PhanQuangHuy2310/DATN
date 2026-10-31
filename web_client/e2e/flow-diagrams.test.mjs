import test from "node:test";
import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { FLOW_DIAGRAMS, TYPE_LIFECYCLES, relevantDiagrams, resolveLifecycle } from "../src/flowDiagrams.js";
import { canNavigate } from "../src/rolePolicy.js";

const valid = new Set(["A", "B", "C"]);
test("all workflow diagrams are bundled and have unique slugs", () => {
  assert.equal(FLOW_DIAGRAMS.length, 9);
  assert.equal(new Set(FLOW_DIAGRAMS.map(({ id }) => id)).size, FLOW_DIAGRAMS.length);
  for (const diagram of FLOW_DIAGRAMS) {
    assert.ok(existsSync(new URL(`../public/flow-diagrams/${diagram.id}.webp`, import.meta.url)), `Missing ${diagram.id}`);
  }
});
test("each of the 18 plan types maps to a source-approved lifecycle", () => {
  assert.equal(Object.keys(TYPE_LIFECYCLES).length, 18);
  assert.ok(Object.values(TYPE_LIFECYCLES).every((value) => valid.has(value)));
});
test("live workflow lifecycle takes precedence over catalog fallback", () => {
  assert.equal(resolveLifecycle({ type_code: "LEAVE_ANNUAL", workflow: { lifecycle: "C" } }), "C");
  assert.equal(resolveLifecycle({ type_code: "LEAVE_ANNUAL" }), "A");
  assert.equal(resolveLifecycle({ type_code: "NON_EXISTENT_TYPE" }), null);
  assert.equal(resolveLifecycle({ type_code: "NON_EXISTENT_TYPE" }, "B"), "B");
});
test("request view only shows its own matching lifecycle", () => {
  const entries = relevantDiagrams({type_code: "LEAVE_ANNUAL",workflow:{lifecycle:"B"}});
  assert.ok(entries.some((item) => item.id === "lifecycle-b"));
  assert.ok(!entries.some((item) => item.id === "lifecycle-a"));
  assert.ok(!entries.some((item) => item.id === "admin"));
});
test("read-only diagram library is accessible to known roles, not unknown roles", () => {
  for (const role of ["REQUESTER", "APPROVER", "EXECUTOR", "ACCEPTOR", "POLICY_ADMIN", "OPS_ADMIN", "AUDITOR"]) {
    assert.equal(canNavigate([role], "flow-diagrams"), true);
  }
  assert.equal(canNavigate(["NOT_REGISTERED"], "flow-diagrams"), false);
});
