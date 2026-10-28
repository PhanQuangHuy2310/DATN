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
    };
  }
  if (action === "cancel") return { ...body, reason: values.reason };
  if (action === "claim") return body;
  if (action === "issue") {
    return { ...body, kind: values.kind, reason: values.reason };
  }
  throw new TypeError(`Unsupported request action: ${action}`);
}
