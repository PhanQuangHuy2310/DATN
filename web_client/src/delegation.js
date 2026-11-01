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
