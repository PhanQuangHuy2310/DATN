import test from "node:test";
import assert from "node:assert/strict";
import { parsePolicyFile } from "../src/aiPolicy.js";
import { canNavigate } from "../src/rolePolicy.js";

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

test("only POLICY_ADMIN reaches the AI policy page", () => {
  assert.equal(canNavigate(["POLICY_ADMIN"], "ai-policy"), true);
  for (const role of ["OPS_ADMIN", "AUDITOR", "APPROVER", "REQUESTER"]) {
    assert.equal(canNavigate([role], "ai-policy"), false);
  }
});
