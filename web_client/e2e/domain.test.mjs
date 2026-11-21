import test from "node:test";
import assert from "node:assert/strict";
import { canMarkEscalationWrong, permissions, statuses } from "../src/domain.js";
const me = { id: "me", roles: ["REQUESTER", "APPROVER", "EXECUTOR", "ACCEPTOR"] };
const activeApproval = { requester_id: "requester", status:"PENDING_APPROVAL", approval_steps: [{state:"ACTIVE",assignee_id:"me"}] };
const executionReady = { requester_id:"requester", approval_steps: [{state:"APPROVED",assignee_id:"approver"}], workflow:{ lifecycle:"C",acceptor_id:"acceptor",attempt:{executor_id:"me",state:"READY"}}, status:"READY_FOR_EXECUTION"};
const executionRunning = {...executionReady, status:"IN_PROGRESS", workflow:{...executionReady.workflow,attempt:{executor_id:"me",state:"RUNNING"}}};
const submitted = {...executionReady, status:"WAITING_FOR_ACCEPTANCE", workflow:{...executionReady.workflow,acceptor_id:"me",attempt:{executor_id:"other",state:"SUBMITTED"}}};
test("terminal states allow no mutations", () => {
  for (const status of ["COMPLETED", "CANCELLED", "REJECTED"])
    assert.ok(Object.values(permissions(me, { ...submitted, status })).every((v) => !v));
});
test("cancel limited to owner before final approval", () => {
  const own = {...activeApproval, requester_id:"me"};
  for (const status of Object.keys(statuses))
    assert.equal(permissions(me, {...own,status}).cancel,["DRAFT", "NEEDS_INFO", "PENDING_APPROVAL"].includes(status));
  assert.equal(permissions({...me,id:"other"}, {...own,status:"DRAFT"}).cancel,false);
});
test("role alone cannot act on another assignment", () => {
  const other = {...me,id:"different"};
  assert.equal(permissions(other,activeApproval).approve,false);
  assert.equal(permissions(other,executionReady).claim,false);
  assert.equal(permissions(other,submitted).accept,false);
});
test("claim, execute and accept have different FSM guards", () => {
  assert.equal(permissions(me,executionReady).claim,true);
  assert.equal(permissions(me,executionRunning).execute,true);
  assert.equal(permissions(me,submitted).accept,true);
  assert.equal(permissions(me,executionRunning).accept,false);
});
test("role revoked cannot mutate own request", () => {
  assert.equal(permissions({id:"me",roles:[]}, {...activeApproval,requester_id:"me",status:"DRAFT"}).edit,false);
});
test("SoD: requester cannot approve own request even if assigned", () => {
  assert.equal(permissions(me,{...activeApproval,requester_id:"me"}).approve,false);
});
test("SoD: executor cannot be requester or former approver", () => {
  assert.equal(permissions(me,{...executionReady,requester_id:"me"}).claim,false);
  assert.equal(permissions(me,{...executionRunning, approval_steps:[{state:"APPROVED",assignee_id:"me"}]}).execute,false);
});
test("SoD: executor cannot accept own execution attempt", () => {
  const selfAccept = {...submitted, workflow:{...submitted.workflow, attempt:{...submitted.workflow.attempt,executor_id:"me"}}};
  assert.equal(permissions(me,selfAccept).accept,false);
});

test("revoke AI approval button shows only within 24h for a non-requester approver", () => {
  const soon = new Date(Date.now() + 3600_000).toISOString();
  const past = new Date(Date.now() - 60_000).toISOString();
  const aiDone = (until, revocable = true) => ({
    requester_id: "requester", status: "COMPLETED", approval_steps: [],
    ai_auto_approval: { revocable, revocable_until: until },
  });
  assert.equal(permissions(me, aiDone(soon)).revokeAi, true);
  assert.equal(permissions(me, aiDone(past)).revokeAi, false);
  assert.equal(permissions(me, aiDone(soon, false)).revokeAi, false);
  assert.equal(permissions({ ...me, id: "requester" }, aiDone(soon)).revokeAi, false);
  assert.equal(permissions({ id: "x", roles: ["REQUESTER"] }, aiDone(soon)).revokeAi, false);
});

test("AI chuyển nhầm button follows per-request role: hidden for requester, shown only for reviewer of that request", () => {
  const u1 = { id: "u1", roles: ["REQUESTER", "APPROVER"] };
  const escalated = { from_lifecycle: "A", to_lifecycle: "B", causes: [], can_mark_unnecessary: true };

  // Vòng đời 1: u1 là người gửi yêu cầu -> không hiện nút dù AI trả về hoặc trong approval_steps có gì
  const lifecycle1 = {
    requester_id: "u1",
    approval_steps: [{ state: "ACTIVE", assignee_id: "u1" }],
    ai_escalation: escalated,
  };
  assert.equal(canMarkEscalationWrong(u1, lifecycle1), false);

  // Vòng đời 2: cùng u1 nhưng là người kiểm duyệt của yêu cầu do u2 gửi -> hiện nút
  const lifecycle2 = {
    requester_id: "u2",
    approval_steps: [{ state: "ACTIVE", assignee_id: "u1" }],
    ai_escalation: escalated,
  };
  assert.equal(canMarkEscalationWrong(u1, lifecycle2), true);

  // Đã đánh dấu rồi -> không hiện nút nữa
  assert.equal(
    canMarkEscalationWrong(u1, { ...lifecycle2, ai_escalation: { ...escalated, already_marked: true } }),
    false,
  );

  // Không phải người kiểm duyệt -> không hiện nút
  assert.equal(
    canMarkEscalationWrong({ id: "u3", roles: ["APPROVER"] }, {
      ...lifecycle2,
      ai_escalation: { ...escalated, can_mark_unnecessary: false },
    }),
    false,
  );

  // Không có banner AI chuyển quy trình -> false
  assert.equal(canMarkEscalationWrong(u1, { requester_id: "u2" }), false);
});
