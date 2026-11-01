// Request bodies the UI sends to the API, built from form values (pure functions).
/**
 * Contract used by workflow/service.py: approval and acceptance bodies include
 * `reason` even when an affirmative decision deliberately sets it to null.
 * Avoid forwarding unrelated FormData keys to strict backend validators.
 */
export function requestActionPayload(action, expectedVersion, values = {}) {
  if (!Number.isInteger(expectedVersion)) {
    throw new TypeError("expected_version is required");
  }
  const body = { expected_version: expectedVersion };
  if (["approve", "reject", "info", "accept", "rework"].includes(action)) {
    const outcome = {
      approve: "APPROVE", reject: "REJECT", info: "NEEDS_INFO",
      accept: "ACCEPT", rework: "REWORK",
    }[action];
    return {
      ...body,
      outcome,
      reason: ["approve", "accept"].includes(action) ? null : values.reason,
      ...(action === "approve" && values.executor_id ? { executor_id: values.executor_id } : {}),
    };
  }
  if (action === "cancel" || action === "revokeAi") return { ...body, reason: values.reason };
  if (action === "claim") return body;
  if (action === "issue") {
    return { ...body, kind: values.kind, reason: values.reason };
  }
  throw new TypeError(`Unsupported request action: ${action}`);
}

/** Build the POST /api/v1/delegations body from the form (local time inputs). */
export function delegationBody(values) {
  const toIso = (value) => {
    const parsed = new Date(value);
    if (!value || Number.isNaN(parsed.getTime())) throw new Error("Thời gian không hợp lệ.");
    return parsed.toISOString();
  };
  const starts = toIso(values.starts_at);
  const ends = toIso(values.ends_at);
  if (ends <= starts) throw new Error("Thời điểm kết thúc phải sau thời điểm bắt đầu.");
  return {
    delegate_id: values.delegate_id,
    starts_at: starts,
    ends_at: ends,
    reason: (values.reason || "").trim(),
  };
}

export const delegationActive = (item, now = Date.now()) =>
  !item.revoked_at && Date.parse(item.starts_at) <= now && now < Date.parse(item.ends_at);

/** Parse an uploaded policy file into the API body; throws a Vietnamese message. */
export function parsePolicyFile(text, versionOverride = "") {
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    throw new Error("Tệp không phải JSON hợp lệ.");
  }
  const rules = Array.isArray(data) ? data : data?.rules;
  const version = (versionOverride || data?.version || "").trim();
  if (!Array.isArray(rules)) throw new Error("Tệp phải có mảng \"rules\".");
  if (!version) throw new Error("Cần nhập mã phiên bản (version).");
  return { version, rules };
}
