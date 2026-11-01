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
