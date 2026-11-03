import { useState } from "react";
import { api } from "../api.js";
import { errorText } from "../domain.js";

const OCR_MIME = new Set(["image/jpeg", "image/png", "image/webp", "image/tiff"]);
const FIELD_LABELS = { amount: "Số tiền", invoice_date: "Ngày hóa đơn", invoice_number: "Số hóa đơn", vendor_name: "Nhà cung cấp", tax_code: "Mã số thuế" };
const ENGINES = { paddleocr: "PaddleOCR (cục bộ)", "gemini-vision": "Gemini Vision (dịch vụ ngoài)" };
// Form fields an OCR amount may fill, in the same order the backend reads them.
export const AMOUNT_FIELDS = ["amount_vnd", "amount", "estimated_budget", "refund_amount", "contract_value", "estimated_cost", "estimated_price"];

export function canOcr(attachment) {
  return attachment?.scan_state === "CLEAN" && OCR_MIME.has(attachment?.mime);
}

/** Reads an invoice image through the internal OCR service. The result is a
 * suggestion: nothing changes until the user applies it, and it is recorded
 * in the request's activity log. */
export default function AttachmentOcr({ attachment, onApplyAmount }) {
  const [state, setState] = useState({ busy: false, error: "", result: null });
  if (!canOcr(attachment)) return null;
  async function run() {
    setState({ busy: true, error: "", result: null });
    try {
      const body = await api(`/api/v1/attachments/${attachment.id}/ocr`, { method: "POST", body: "{}", timeoutMs: 130000 });
      setState({ busy: false, error: "", result: body.ocr });
    } catch (error) {
      setState({ busy: false, error: errorText(error), result: null });
    }
  }
  const fields = state.result?.extracted_fields || {};
  return <div className="ocr-box">
    <button type="button" className="secondary" onClick={run} disabled={state.busy}>{state.busy ? "Đang đọc hóa đơn…" : "Đọc hóa đơn (OCR)"}</button>
    {state.error && <p className="error" role="alert">{state.error}</p>}
    {state.result && <div className="ocr-result" aria-live="polite">
      <small className="muted">Công cụ: {ENGINES[state.result.engine] || state.result.engine}{state.result.confidence != null ? ` · độ tin cậy ${Math.round(state.result.confidence * 100)}%` : " · không có độ tin cậy"}</small>
      {Object.keys(fields).length ? <dl className="data-list">{Object.entries(fields).map(([key, value]) => <div key={key}>
        <dt>{FIELD_LABELS[key] || key}</dt><dd>{key === "amount" ? `${Number(value).toLocaleString("vi-VN")} VNĐ` : String(value)}</dd>
      </div>)}</dl> : <p className="muted">Không nhận diện được trường nào; hãy kiểm tra ảnh hoặc nhập tay.</p>}
      {onApplyAmount && fields.amount != null && <button type="button" onClick={() => onApplyAmount(fields.amount)}>Điền số tiền vào biểu mẫu</button>}
      <small className="muted">Kết quả OCR chỉ là gợi ý; hãy đối chiếu với chứng từ gốc trước khi gửi.</small>
    </div>}
  </div>;
}
