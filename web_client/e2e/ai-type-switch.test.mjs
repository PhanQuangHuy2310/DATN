import test from "node:test";
import assert from "node:assert/strict";
import {
  carriedValues,
  decideTypeSwitch,
  intentText,
  isNewNeed,
  offerNewType,
  suggestTypes,
} from "../src/aiTypeSwitch.js";

const allowed = ["LEAVE", "LEAVE_SPECIAL", "EXPENSE_CLAIM", "AI_9EFAD2ED"];
const bereavement = {
  predicted_request_type: "LEAVE_SPECIAL",
  confidence_request_type: 0.93,
  low_confidence: false,
  fallback_used: false,
};

test("'bố mất' typed in another form is only suggested, never switched automatically", () => {
  const decision = decideTypeSwitch({ result: bereavement, currentType: "EXPENSE_CLAIM", allowedTypes: allowed });
  assert.deepEqual(decision, { code: "LEAVE_SPECIAL", confidence: 0.93 });
  assert.equal("action" in decision, false);
});

test("after 'Bỏ qua' the same text is not suggested again", () => {
  const decision = decideTypeSwitch({
    result: bereavement, currentType: "EXPENSE_CLAIM", allowedTypes: allowed, dismissed: true,
  });
  assert.equal(decision, null);
});

test("no suggestion for the same type, an unsure model, the keyword fallback, a new need or a forbidden type", () => {
  const base = { currentType: "EXPENSE_CLAIM", allowedTypes: allowed };
  assert.equal(decideTypeSwitch({ ...base, result: { ...bereavement, predicted_request_type: "EXPENSE_CLAIM" } }), null);
  assert.equal(decideTypeSwitch({ ...base, result: { ...bereavement, low_confidence: true } }), null);
  assert.equal(decideTypeSwitch({ ...base, result: { ...bereavement, fallback_used: true } }), null);
  assert.equal(decideTypeSwitch({ ...base, result: { ...bereavement, novel: true } }), null);
  assert.equal(decideTypeSwitch({ ...base, result: { ...bereavement, predicted_request_type: "SALARY_ADJUSTMENT" } }), null);
});

test("a weak guess is not suggested; a clear winner is ('bo mat' typed without accents)", () => {
  const base = { currentType: "EXPENSE_CLAIM", allowedTypes: allowed };
  const winner = {
    predicted_request_type: "LEAVE_SPECIAL",
    confidence_request_type: 0.3991,
    alternatives: [
      { request_type: "LEAVE_SPECIAL", confidence: 0.3991 },
      { request_type: "FACILITY_REPAIR", confidence: 0.1102 },
    ],
  };
  assert.deepEqual(decideTypeSwitch({ ...base, result: winner }), { code: "LEAVE_SPECIAL", confidence: 0.3991 });
  assert.equal(offerNewType(winner), false);
  const close = { ...winner, alternatives: [winner.alternatives[0], { request_type: "LEAVE", confidence: 0.26 }] };
  assert.equal(decideTypeSwitch({ ...base, result: close }), null);
  assert.equal(offerNewType(close), true);
  assert.equal(offerNewType(bereavement), false);
  assert.equal(offerNewType({ ...bereavement, unclear: true }), false);
});

test("a type learned after training is suggested even though the base model judged the need new", () => {
  const learned = {
    predicted_request_type: "AI_9EFAD2ED", confidence_request_type: 0.81, low_confidence: false,
    novel: false, source: "learned",
  };
  assert.deepEqual(
    decideTypeSwitch({ result: learned, currentType: "LEAVE", allowedTypes: allowed }),
    { code: "AI_9EFAD2ED", confidence: 0.81 },
  );
  assert.equal(isNewNeed(learned), false);
  assert.equal(isNewNeed({ ...learned, source: "model", novel: true }), true);
  assert.equal(isNewNeed({ novel: true, unclear: true }), false);
});

const catalog = [
  { code: "LEAVE", name: "Nghỉ phép" },
  { code: "LEAVE_SPECIAL", name: "Nghỉ phép đặc biệt" },
  { code: "AI_9EFAD2ED", name: "Đăng ký suất ăn trưa" },
];

test("'Có phải ý bạn là' lists creatable types, best first, without duplicates", () => {
  const result = {
    ...bereavement,
    predicted_request_name: "Nghỉ phép đặc biệt",
    alternatives: [
      { request_type: "LEAVE_SPECIAL", name: "x", confidence: 0.93 },
      { request_type: "LEAVE", name: "x", confidence: 0.4 },
      { request_type: "SALARY_ADJUSTMENT", name: "x", confidence: 0.3 },
      { request_type: "EXPENSE_CLAIM", name: "x", confidence: 0.05 },
    ],
  };
  assert.deepEqual(suggestTypes(result, catalog), [
    { code: "LEAVE_SPECIAL", name: "Nghỉ phép đặc biệt", confidence: 0.93 },
    { code: "LEAVE", name: "Nghỉ phép", confidence: 0.4 },
  ]);
});

test("for a new need only learned types are offered; unclear text offers nothing", () => {
  const result = {
    predicted_request_type: "LAPTOP_PROVISION", confidence_request_type: 0.84, novel: true, source: "model",
    alternatives: [
      { request_type: "LAPTOP_PROVISION", confidence: 0.84, source: "model" },
      { request_type: "AI_9EFAD2ED", confidence: 0.32, source: "learned" },
    ],
  };
  assert.deepEqual(suggestTypes(result, catalog), [
    { code: "AI_9EFAD2ED", name: "Đăng ký suất ăn trưa", confidence: 0.32 },
  ]);
  assert.deepEqual(suggestTypes({ ...result, unclear: true }, catalog), []);
  assert.deepEqual(suggestTypes({ ...result, fallback_used: true }, catalog), []);
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
