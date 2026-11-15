import test from "node:test";
import assert from "node:assert/strict";
import {
  AUTO_SWITCH_CONFIDENCE,
  carriedValues,
  decideTypeSwitch,
  intentText,
} from "../src/aiTypeSwitch.js";

const allowed = ["LEAVE", "LEAVE_SPECIAL", "EXPENSE_CLAIM"];
const bereavement = {
  predicted_request_type: "LEAVE_SPECIAL",
  confidence_request_type: 0.93,
  low_confidence: false,
  fallback_used: false,
};

test("'bố mất' typed in any empty form switches to the special leave form", () => {
  const decision = decideTypeSwitch({
    result: bereavement, currentType: "EXPENSE_CLAIM", allowedTypes: allowed, pristine: true, dismissed: false,
  });
  assert.deepEqual(decision, { action: "auto", code: "LEAVE_SPECIAL", confidence: 0.93 });
});

test("a form the user already filled is only offered the switch", () => {
  const decision = decideTypeSwitch({
    result: bereavement, currentType: "EXPENSE_CLAIM", allowedTypes: allowed, pristine: false, dismissed: false,
  });
  assert.equal(decision.action, "suggest");
});

test("after an undo the same text is not switched again automatically", () => {
  const decision = decideTypeSwitch({
    result: bereavement, currentType: "EXPENSE_CLAIM", allowedTypes: allowed, pristine: true, dismissed: true,
  });
  assert.equal(decision.action, "suggest");
});

test("no switch for the same type, an unsure model, the keyword fallback or a forbidden type", () => {
  const base = { currentType: "EXPENSE_CLAIM", allowedTypes: allowed, pristine: true, dismissed: false };
  assert.equal(decideTypeSwitch({ ...base, result: { ...bereavement, predicted_request_type: "EXPENSE_CLAIM" } }), null);
  assert.equal(decideTypeSwitch({ ...base, result: { ...bereavement, low_confidence: true } }), null);
  assert.equal(decideTypeSwitch({ ...base, result: { ...bereavement, fallback_used: true } }), null);
  assert.equal(decideTypeSwitch({ ...base, result: { ...bereavement, predicted_request_type: "SALARY_ADJUSTMENT" } }), null);
  const unsure = decideTypeSwitch({
    ...base,
    result: {
      ...bereavement,
      confidence_request_type: AUTO_SWITCH_CONFIDENCE - 0.01,
      alternatives: [{ request_type: "LEAVE", confidence: 0.3 }],
    },
  });
  assert.equal(unsure.action, "suggest");
});

test("a clear winner below 60% still switches ('bo mat' typed without accents)", () => {
  const result = {
    predicted_request_type: "LEAVE_SPECIAL",
    confidence_request_type: 0.3991,
    alternatives: [
      { request_type: "LEAVE_SPECIAL", confidence: 0.3991 },
      { request_type: "FACILITY_REPAIR", confidence: 0.1102 },
      { request_type: "IT_SUPPORT", confidence: 0.0757 },
    ],
  };
  const base = { currentType: "EXPENSE_CLAIM", allowedTypes: allowed, pristine: true, dismissed: false };
  assert.equal(decideTypeSwitch({ ...base, result }).action, "auto");
  const close = { ...result, alternatives: [result.alternatives[0], { request_type: "LEAVE", confidence: 0.3 }] };
  assert.equal(decideTypeSwitch({ ...base, result: close }).action, "suggest");
});

test("intent text needs a few characters and joins title and reason", () => {
  assert.equal(intentText({ title: "bố" }), "");
  assert.equal(intentText({ title: "bố mất" }), "bố mất");
  assert.equal(intentText({ title: "bố mất", reason: "về quê lo tang" }), "bố mất. về quê lo tang");
});

test("carried values keep typed text but drop presets, files and the submit button", () => {
  const values = carriedValues(
    [["title", "bố mất"], ["reason", " "], ["app_code", "ERP"], ["action", "send"], ["file", {}]],
    { app_code: "ERP" },
  );
  assert.deepEqual(values, { title: "bố mất" });
});
