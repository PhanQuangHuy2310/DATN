/** Mẫu nạp nhanh quy định: từ vài lựa chọn sinh ra một câu điều khoản đúng cách viết mà AI hiểu chắc chắn
 * (api_core/workflow/regulation_compiler.py). Kiểm thử: e2e/regulation-template.test.mjs và
 * tests/test_regulation_template.py (cùng các câu mẫu, biên dịch thật). */

export const CONDITIONS = [
  { id: "amount", label: "Số tiền", unit: "triệu đồng" },
  { id: "days", label: "Số ngày", unit: "ngày" },
  { id: "percent", label: "Mức chiết khấu / tỉ lệ", unit: "%" },
  { id: "repeat", label: "Số lần trong tháng", unit: "lần" },
  { id: "all", label: "Mọi hồ sơ của loại này", unit: "" },
];
export const OPERATORS = [
  { id: "gt", label: "trên" },
  { id: "gte", label: "từ … trở lên" },
  { id: "lt", label: "dưới" },
  { id: "lte", label: "không quá" },
];
export const ACTIONS = [
  { id: "manual", label: "Bắt buộc người duyệt thủ công" },
  { id: "acceptance", label: "Người duyệt thủ công + nghiệm thu độc lập (quy trình C)" },
  { id: "auto", label: "Cho AI tự động duyệt" },
];
export const APPROVERS = ["Trưởng bộ phận", "Kế toán", "Giám đốc", "Phòng nhân sự"];

function number(value) {
  const n = Number(String(value).replace(",", "."));
  return Number.isFinite(n) && n > 0 ? n : null;
}

function condition(cond, op, value) {
  if (cond === "all") return "";
  const n = number(value);
  if (n === null) return null;
  if (cond === "repeat") return ` lần thứ ${Math.round(n)} trở lên trong tháng`;
  const unit = cond === "amount" ? " triệu đồng" : cond === "days" ? " ngày" : "%";
  const lead = cond === "amount" ? " có giá trị" : cond === "percent" ? " có mức" : "";
  const qty = `${n}${unit}`;
  if (op === "gte") return `${lead} từ ${qty} trở lên`;
  const word = { gt: "trên", lt: "dưới", lte: "không quá" }[op] || "trên";
  return `${lead} ${word} ${qty}`;
}

function action(act, approver) {
  if (act === "auto") return "được tự động duyệt";
  const who = APPROVERS.includes(approver) ? approver : "Trưởng bộ phận";
  return act === "acceptance"
    ? `bắt buộc ${who} phê duyệt thủ công kèm nghiệm thu độc lập`
    : `bắt buộc ${who} phê duyệt thủ công`;
}

/** Câu điều khoản, hoặc null khi thiếu thông tin. Không cho "AI tự duyệt" kèm điều kiện lặp lại (AI không mở rộng
 * tự duyệt theo ngữ cảnh). */
export function buildClause({ typeName, cond, op, value, act, approver }, index = 1) {
  if (!typeName) return null;
  if (act === "auto" && cond === "repeat") return null;
  const c = condition(cond, op, value);
  if (c === null) return null;
  const prefix = cond === "all" ? `Mọi yêu cầu ${typeName}` : `Yêu cầu ${typeName}${c}`;
  return `Điều ${index}: ${prefix} ${action(act, approver)}.`;
}

/** Số điều tiếp theo trong nội dung đang soạn. */
export function nextArticle(content) {
  const nums = [...String(content || "").matchAll(/(?:^|\n)\s*Điều\s+(\d+)/gi)].map((m) => Number(m[1]));
  return nums.length ? Math.max(...nums) + 1 : 1;
}
