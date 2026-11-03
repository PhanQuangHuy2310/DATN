import test from "node:test";
import assert from "node:assert/strict";
import { visiblePages, canNavigate, roleTasks, ROLE_NAVIGATION } from "../src/rolePolicy.js";

const ROLES = ["REQUESTER", "APPROVER", "EXECUTOR", "ACCEPTOR", "POLICY_ADMIN", "OPS_ADMIN", "AUDITOR"];

test("each of the seven SRS roles has the correct main worklist", () => {
  const worklists = {
    REQUESTER: "mine", APPROVER: "approval", EXECUTOR: "execution", ACCEPTOR: "acceptance",
    POLICY_ADMIN: "policy", OPS_ADMIN: "ops", AUDITOR: "audit",
  };
  for (const role of ROLES) {
    assert.ok(canNavigate([role], worklists[role]), role);
    assert.ok(roleTasks([role]).some((entry) => entry.page === worklists[role]), role);
  }
});

test("auditors cannot see mutation workspaces", () => {
  const pages = visiblePages(["AUDITOR"]);
  // "team" is a read-only scoped report (UC15: auditor is the primary report actor).
  assert.deepEqual(pages, ["home", "flow-diagrams", "ai-process", "team", "team-employees", "audit", "events", "notifications", "profile"]);
  for (const mutation of ["approval", "execution", "acceptance"]) assert.ok(!pages.includes(mutation));
  assert.ok(!pages.includes("mine"));
  assert.ok(!pages.includes("ops"));
  assert.ok(!pages.includes("policy"));
});

test("policy admin does not inherit ops, requester or audit features", () => {
  for (const p of ["mine", "ops", "identity", "approval", "audit"]) assert.equal(canNavigate(["POLICY_ADMIN"], p), false);
});

test("role union works for multi-role users without duplicates", () => {
  const pages = visiblePages(["REQUESTER", "ACCEPTOR", "OPS_ADMIN"]);
  assert.ok(pages.includes("mine") && pages.includes("acceptance") && pages.includes("ops"));
  assert.equal(new Set(pages).size, pages.length);
});

test("unknown role cannot gain privileged navigation", () => {
  assert.deepEqual(visiblePages(["SOME_UNKNOWN_ROLE"]), ["home", "notifications", "profile"]);
  assert.ok(Object.keys(ROLE_NAVIGATION).length === 7);
});

test("UC17 identity console requires an explicit GLOBAL+ALL capability", () => {
  assert.equal(canNavigate(["OPS_ADMIN"], "identity"), false);
  assert.equal(canNavigate(["OPS_ADMIN"], "identity", {identity_manage:true}), true);
  assert.equal(canNavigate(["REQUESTER"], "identity", {identity_manage:true}), false);
  assert.equal(roleTasks(["OPS_ADMIN"]).some(t => t.page === "identity"), false);
  assert.equal(roleTasks(["OPS_ADMIN"], {identity_manage:true}).some(t => t.page === "identity"), true);
});

test("UC17 API catalog and matrix require GLOBAL+ALL ops capability", () => {
  assert.equal(canNavigate(["OPS_ADMIN"], "api-admin"), false);
  assert.equal(canNavigate(["OPS_ADMIN"], "api-admin", {identity_manage:true}), true);
  assert.equal(canNavigate(["AUDITOR"], "api-admin", {identity_manage:true}), false);
  assert.ok(!visiblePages(["POLICY_ADMIN", "AUDITOR"]).includes("api-admin"));
  assert.ok(roleTasks(["OPS_ADMIN"], {identity_manage:true}).some(t => t.page === "api-admin"));
});


test("Plan request blueprints are available only to policy/operations admins", () => {
  for (const role of ["POLICY_ADMIN", "OPS_ADMIN"]) assert.equal(canNavigate([role], "plan-catalog"), true);
  for (const role of ["REQUESTER", "APPROVER", "EXECUTOR", "ACCEPTOR", "AUDITOR"]) assert.equal(canNavigate([role], "plan-catalog"), false);
});


test("new admin workspaces require global identity authority", () => {
  for (const page of ["users", "permissions", "request-catalog"]) {
    assert.equal(canNavigate(["OPS_ADMIN"],page),false);
    assert.equal(canNavigate(["OPS_ADMIN"],page,{identity_manage:true}),true);
    assert.equal(canNavigate(["REQUESTER"],page,{identity_manage:true}),false);
  }
});
test("AI process guide is available to every recognized role", () => {
  for (const role of ROLES) assert.equal(canNavigate([role],"ai-process"),true);
});

test("portal access: pure admins stay in the admin portal, admins with duties use both", async () => {
  const { canUsePortal } = await import("../src/rolePolicy.js");
  const pureAdmin = ["OPS_ADMIN", "POLICY_ADMIN", "REQUESTER", "ACCEPTOR"];
  const auditorApprover = ["AUDITOR", "APPROVER", "REQUESTER", "ACCEPTOR"];
  const opsExecutor = ["OPS_ADMIN", "EXECUTOR", "REQUESTER"];
  const employee = ["REQUESTER", "APPROVER", "ACCEPTOR"];
  assert.equal(canUsePortal(pureAdmin, "admin"), true);
  assert.equal(canUsePortal(pureAdmin, "client"), false);
  for (const roles of [auditorApprover, opsExecutor]) {
    assert.equal(canUsePortal(roles, "admin"), true);
    assert.equal(canUsePortal(roles, "client"), true);
  }
  assert.equal(canUsePortal(employee, "client"), true);
  assert.equal(canUsePortal(employee, "admin"), false);
  assert.equal(canUsePortal(undefined, "client"), true);
});

test("only POLICY_ADMIN reaches the AI policy page", () => {
  assert.equal(canNavigate(["POLICY_ADMIN"], "ai-policy"), true);
  for (const role of ["OPS_ADMIN", "AUDITOR", "APPROVER", "REQUESTER"]) {
    assert.equal(canNavigate([role], "ai-policy"), false);
  }
});

test("department dashboard is limited to approvers and auditors", () => {
  assert.ok(canNavigate(["APPROVER"], "team"));
  assert.ok(canNavigate(["AUDITOR"], "team"));
  for (const role of ["REQUESTER", "EXECUTOR", "ACCEPTOR", "POLICY_ADMIN", "OPS_ADMIN"]) assert.equal(canNavigate([role], "team"), false, role);
});
