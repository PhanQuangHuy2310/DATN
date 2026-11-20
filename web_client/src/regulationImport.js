/** Nhập file quy định viết sẵn + so sánh hai bản nội dung (dùng cho lịch sử thay đổi). */

export const IMPORT_ACCEPT = ".txt,.md,.docx,text/plain,text/markdown,application/vnd.openxmlformats-officedocument.wordprocessingml.document";
export const IMPORT_MAX_BYTES = 2 * 1024 * 1024;

/** File mẫu để admin viết trước rồi chỉ việc tải lên. Dòng "Mã:", "Danh mục:" là tùy chọn. */
export const IMPORT_TEMPLATE = [
  "QUY ĐỊNH VỀ NGHỈ PHÉP VÀ THANH TOÁN",
  "Mã: QD-MAU-01",
  "Danh mục: Thời gian & Nghỉ phép",
  "",
  "Điều 1: Yêu cầu Nghỉ phép từ 5 ngày trở lên bắt buộc Trưởng bộ phận phê duyệt thủ công.",
  "Điều 2: Yêu cầu Thanh toán chi phí có giá trị dưới 2 triệu đồng được tự động duyệt.",
  "Điều 3: Yêu cầu Thanh toán chi phí có giá trị trên 10 triệu đồng bắt buộc Giám đốc phê duyệt thủ công.",
  "",
].join("\n");

export function bytesToBase64(bytes) {
  let binary = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}

/** Diff theo dòng (LCS). Trả về [{kind: "same"|"add"|"del", text}]. */
export function lineDiff(before, after) {
  const a = String(before || "").split("\n");
  const b = String(after || "").split("\n");
  const n = a.length;
  const m = b.length;
  const lcs = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i -= 1) {
    for (let j = m - 1; j >= 0; j -= 1) {
      lcs[i][j] = a[i] === b[j] ? lcs[i + 1][j + 1] + 1 : Math.max(lcs[i + 1][j], lcs[i][j + 1]);
    }
  }
  const out = [];
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) {
      out.push({ kind: "same", text: a[i] });
      i += 1;
      j += 1;
    } else if (lcs[i + 1][j] >= lcs[i][j + 1]) {
      out.push({ kind: "del", text: a[i] });
      i += 1;
    } else {
      out.push({ kind: "add", text: b[j] });
      j += 1;
    }
  }
  while (i < n) out.push({ kind: "del", text: a[i++] });
  while (j < m) out.push({ kind: "add", text: b[j++] });
  return out.filter((line) => line.text.trim() || line.kind === "same");
}

export const ACTION_LABELS = {
  CREATE: "Thêm mới",
  UPDATE_MINOR: "Sửa",
  UPDATE_MAJOR: "Sửa (cập nhật lớn)",
  DELETE_MAJOR: "Gỡ bỏ",
};
