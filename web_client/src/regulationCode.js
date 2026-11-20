/** Mã REG-NNN kế tiếp chưa có trong danh sách (dự phòng khi API chưa trả next_code). */
export function freeCode(regulations) {
  const used = new Set((regulations || []).map((r) => String(r.code || "").toUpperCase()));
  let n = Math.max(0, ...[...used].map((c) => Number(/^REG-(\d+)$/.exec(c)?.[1] || 0))) + 1;
  while (used.has(`REG-${String(n).padStart(3, "0")}`)) n += 1;
  return `REG-${String(n).padStart(3, "0")}`;
}
