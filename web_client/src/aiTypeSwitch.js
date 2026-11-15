/** When the AI classifier should move the user to another request form.
 *
 * The employee may open any form and just type "bố mất" in the title: the
 * classifier recognises a bereavement leave and the editor switches to the
 * "Nghỉ phép đặc biệt" form, carrying the title and reason over.
 *
 * - "auto": the form is still empty apart from title/reason, the model is sure
 *   (>= AUTO_SWITCH_CONFIDENCE, or a clear winner: >= CLEAR_WINNER_MIN and
 *   CLEAR_WINNER_RATIO times the runner-up, e.g. "bo mat" typed without
 *   accents) and the user has not undone a switch for this same text.
 * - "suggest": any other confident prediction of a different type; the user
 *   decides with one click.
 * - null: same type, unsure model, keyword fallback or a type the user may not
 *   create.
 */
export const AUTO_SWITCH_CONFIDENCE = 0.6;
export const CLEAR_WINNER_MIN = 0.35;
export const CLEAR_WINNER_RATIO = 3;
export const MIN_CLASSIFY_CHARS = 4;
// Fields whose text describes what the user wants; other fields mean the user
// has already started filling the chosen form.
export const INTENT_FIELDS = new Set(["title", "reason"]);

export function decideTypeSwitch({ result, currentType, allowedTypes, pristine, dismissed }) {
  const code = String(result?.predicted_request_type || "").toUpperCase();
  if (!code || result?.fallback_used || result?.low_confidence) return null;
  if (code === String(currentType || "").toUpperCase()) return null;
  if (Array.isArray(allowedTypes) && !allowedTypes.includes(code)) return null;
  const confidence = Number(result?.confidence_request_type) || 0;
  const action = pristine && !dismissed && isSure(code, confidence, result?.alternatives) ? "auto" : "suggest";
  return { action, code, confidence };
}

function isSure(code, confidence, alternatives) {
  if (confidence >= AUTO_SWITCH_CONFIDENCE) return true;
  const runnerUp = Math.max(
    0,
    ...(Array.isArray(alternatives) ? alternatives : [])
      .filter((item) => String(item?.request_type || "").toUpperCase() !== code)
      .map((item) => Number(item?.confidence) || 0),
  );
  return confidence >= CLEAR_WINNER_MIN && confidence >= CLEAR_WINNER_RATIO * runnerUp;
}

/** Text sent to the classifier, or "" when there is not enough to classify. */
export function intentText(values) {
  const title = String(values?.title || "").trim();
  const reason = String(values?.reason || "").trim();
  const text = [title, reason].filter(Boolean).join(". ");
  return text.length >= MIN_CLASSIFY_CHARS ? text : "";
}

/** Non-empty text values of a form, minus the locked preset fields and the submit action. */
export function carriedValues(entries, preset = {}) {
  const values = {};
  for (const [name, value] of entries) {
    if (name === "action" || name in preset) continue;
    if (typeof value !== "string" || !value.trim()) continue;
    values[name] = value;
  }
  return values;
}
