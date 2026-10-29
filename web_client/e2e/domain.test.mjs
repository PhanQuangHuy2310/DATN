import test from "node:test";
import assert from "node:assert/strict";
import { permissions, statuses } from "../src/domain.js";
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
