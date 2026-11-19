/** What the automatic AI box under the request title offers, and the "Có phải ý bạn là…" list in search.
 *
 * The employee may open any form and just type "bố mất" in the title: the
 * classifier recognises a bereavement leave and the AI box suggests the
 * "Nghỉ phép đặc biệt" form with one button. The editor never switches on its
 * own; the title and reason typed so far are carried over when the user
 * accepts.
 *
 * decideTypeSwitch suggests a form only when the model is sure: at least
 * SURE_CONFIDENCE, or a clear winner (>= CLEAR_WINNER_MIN and CLEAR_WINNER_RATIO
 * times the runner-up, e.g. "bo mat" typed without accents). It returns null for
 * the same type, an unsure model, the keyword fallback, a need the AI judges new
 * to the catalogue, a type the user may not create, or a text the user already
 * dismissed.
 */
export const SURE_CONFIDENCE = 0.5;
export const CLEAR_WINNER_MIN = 0.35;
export const CLEAR_WINNER_RATIO = 3;
export const MIN_CLASSIFY_CHARS = 4;
export const MIN_SUGGEST_CONFIDENCE = 0.2;
// Fields whose text describes what the user wants.
export const INTENT_FIELDS = new Set(["title", "reason"]);

const upper = (value) => String(value || "").toUpperCase();

export function decideTypeSwitch({ result, currentType, allowedTypes, dismissed = false }) {
  const code = upper(result?.predicted_request_type);
  if (!code || dismissed || result?.fallback_used || result?.low_confidence || isNewNeed(result)) return null;
  if (code === upper(currentType)) return null;
  if (Array.isArray(allowedTypes) && !allowedTypes.includes(code)) return null;
  const confidence = Number(result?.confidence_request_type) || 0;
  return isSure(code, confidence, result?.alternatives) ? { code, confidence } : null;
}

/** The prediction is trustworthy enough to act on (suggest a switch, skip the "create a new type" offer). */
export function isSure(code, confidence, alternatives) {
  if (confidence >= SURE_CONFIDENCE) return true;
  const runnerUp = Math.max(
    0,
    ...(Array.isArray(alternatives) ? alternatives : [])
      .filter((item) => upper(item?.request_type) !== upper(code))
      .map((item) => Number(item?.confidence) || 0),
  );
  return confidence >= CLEAR_WINNER_MIN && confidence >= CLEAR_WINNER_RATIO * runnerUp;
}

/** The AI box should offer "Tạo loại yêu cầu mới": a new need, or no type the model is sure about. */
export function offerNewType(result) {
  if (!result || result.fallback_used || result.unclear) return false;
  if (isNewNeed(result)) return true;
  return Boolean(result.low_confidence) ||
    !isSure(result.predicted_request_type, Number(result.confidence_request_type) || 0, result.alternatives);
}

/** The AI found no catalogue type for the text: the model guess is not backed by its vocabulary. */
export function isNewNeed(result) {
  return Boolean(result && !result.fallback_used && !result.unclear && result.novel && result.source !== "learned");
}

/**
 * Types to offer as "Có phải ý bạn là…": the prediction and the alternatives the
 * user may create, best first. When the need is new, only types learned after
 * training (matched by their name and past titles) are offered, since the
 * model's own guess is then unreliable.
 */
export function suggestTypes(result, catalog, limit = 3) {
  if (!result || result.fallback_used || result.unclear) return [];
  const names = new Map((catalog || []).map((item) => [upper(item.code), item.name || item.code]));
  const fresh = isNewNeed(result);
  const candidates = [
    {
      request_type: result.predicted_request_type,
      name: result.predicted_request_name,
      confidence: result.confidence_request_type,
      source: result.source,
    },
    ...(Array.isArray(result.alternatives) ? result.alternatives : []),
  ];
  const seen = new Set();
  const out = [];
  for (const item of candidates) {
    const code = upper(item?.request_type);
    const confidence = Number(item?.confidence) || 0;
    if (!code || seen.has(code) || !names.has(code) || confidence < MIN_SUGGEST_CONFIDENCE) continue;
    if (fresh && item.source !== "learned") continue;
    seen.add(code);
    out.push({ code, name: names.get(code) || item.name || code, confidence });
  }
  return out.sort((a, b) => b.confidence - a.confidence).slice(0, limit);
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
