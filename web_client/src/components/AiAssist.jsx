import { useState } from "react";
import { api, notify } from "../api.js";
import { errorText, types } from "../domain.js";

const RISK_LABELS = { low: "thấp", medium: "trung bình", high: "cao", critical: "rất cao" };

function riskLevel(score) {
  if (score <= 2) return "low";
  if (score <= 3) return "medium";
  return "high";
}

// Colour follows the model's label when it has one, so "2/5 (trung bình)" is never shown in the "low" colour.
function riskTone(risk) {
  const label = String(risk?.risk_label || "").toLowerCase();
  if (label === "critical") return "high";
  return ["low", "medium", "high"].includes(label) ? label : riskLevel(risk?.risk_score);
}

// Bộ phận xử lý do AI suy ra từ catalog (executor của loại yêu cầu).
const departmentLabels = {
  HR: "Nhân sự",
  FINANCE: "Tài chính - Kế toán",
  IT: "Công nghệ thông tin",
  TECH: "Kỹ thuật phát triển",
  ADMIN: "Hành chính",
  ASSET: "Quản lý tài sản",
  PROCUREMENT: "Mua hàng",
  FACILITY: "Cơ sở vật chất",
  LEGAL: "Pháp chế",
  MARKETING: "Marketing",
  SALES: "Kinh doanh",
  WAREHOUSE: "Kho vận",
};

function typeName(code, fallback) {
  return types[code] || fallback || code;
}

/** Payload of /api/v1/ai/risk-score for the form being filled. */
export function riskPayload(type, amount, lifecycle, riskWeight) {
  return {
    request_type: type,
    lifecycle_template: lifecycle || "A",
    risk_weight: Number(riskWeight) || 3,
    amount_vnd: amount,
  };
}

/**
 * Hộp AI tự động ngay dưới ô tiêu đề: gõ tiêu đề/nội dung là AI tự phân loại, gợi ý bộ phận và tuyến duyệt,
 * chấm rủi ro. AI không tự chuyển biểu mẫu; nếu nội dung giống loại khác, AI chỉ đưa nút gợi ý chuyển.
 * Hỗ trợ người gửi, không thay quyết định của người duyệt.
 */
export function AiAutoInsight({ insight, nameOf = typeName, onSwitch, onDismiss, onNewType }) {
  const { status = "idle", classify, risk, suggestion, newNeed, offerNew, failed } = insight || {};
  const unsure = Boolean(offerNew && !newNeed);
  const label = (code, fallback) => nameOf(code, fallback);
  return (
    <div className="ai-auto-insight wide" aria-live="polite">
      <div className="ai-auto-head">
        <span className="ai-auto-badge">AI tự động</span>
        {status === "idle" && <small className="muted">Nhập tiêu đề, AI sẽ tự đánh giá loại yêu cầu, bộ phận xử lý và rủi ro.</small>}
        {status === "running" && <small className="muted" role="status">AI đang phân tích nội dung…</small>}
        {status !== "running" && failed && (
          <small className="muted">AI chưa phản hồi đầy đủ; phần thiếu là dữ liệu dự phòng hoặc chưa có.</small>
        )}
      </div>
      {classify && !classify.fallback_used && !classify.unclear && !newNeed && (
        <p>
          Loại đề xuất: <strong>{label(classify.predicted_request_type, classify.predicted_request_name)}</strong> (độ
          tin cậy {Math.round((classify.confidence_request_type || 0) * 100)}%) · Bộ phận xử lý:{" "}
          <strong>{departmentLabels[classify.predicted_department] || "Bộ phận liên quan"}</strong>
          {classify.alternatives?.length > 1 && (
            <>
              <br />
              <small className="muted">
                {unsure ? "AI chưa chắc chắn, có thể là: " : "Khả năng khác: "}
                {classify.alternatives
                  .filter((item) => item.request_type !== classify.predicted_request_type)
                  .slice(0, 2)
                  .map((item) => `${label(item.request_type, item.name)} (${Math.round(item.confidence * 100)}%)`)
                  .join(", ")}
              </small>
            </>
          )}
          {classify.workflow_suggestion && (
            <>
              <br />
              <em>Gợi ý: {classify.workflow_suggestion}</em>
            </>
          )}
        </p>
      )}
      {classify?.unclear && (
        <p className="muted">AI chưa hiểu nội dung này. Hãy viết rõ nhu cầu, ví dụ: «Xin nghỉ phép 2 ngày về quê».</p>
      )}
      {offerNew && (
        <p className="ai-auto-new">
          {newNeed
            ? "AI chưa thấy loại yêu cầu nào trong hệ thống khớp với nội dung này."
            : "AI chưa chắc loại nào ở trên đúng nhu cầu của bạn. Nếu không loại nào đúng:"}
          {onNewType && (
            <>
              {" "}
              <button type="button" className="secondary" onClick={onNewType}>
                Tạo loại yêu cầu mới
              </button>
            </>
          )}
        </p>
      )}
      {risk && (
        <p>
          Điểm rủi ro:{" "}
          <span className={`badge badge-${riskTone(risk)}`}>
            {risk.risk_score}/5 ({RISK_LABELS[String(risk.risk_label || "").toLowerCase()] || risk.risk_label})
          </span>{" "}
          · Có thể ưu tiên xem xét: <strong>{risk.auto_approve_eligible ? "Có" : "Không"}</strong>
        </p>
      )}
      {suggestion && onSwitch && (
        <div className="ai-auto-switch">
          <span>
            Nội dung giống loại <strong>{label(suggestion.code)}</strong> hơn biểu mẫu đang chọn (độ tin cậy{" "}
            {Math.round(suggestion.confidence * 100)}%).
          </span>
          <button type="button" onClick={() => onSwitch(suggestion.code)}>
            Chuyển sang «{label(suggestion.code)}»
          </button>
          <button type="button" className="secondary" onClick={onDismiss}>
            Bỏ qua
          </button>
          <small className="muted">Tiêu đề và nội dung đã nhập được giữ nguyên.</small>
        </div>
      )}
    </div>
  );
}


export function AiSummary({ request }) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [summary, setSummary] = useState(null),
    [phase, setPhase] = useState("idle");

  async function run() {
    setBusy(true);
    setError("");
    setPhase("running");
    try {
      const res = await api("/api/v1/ai/summarize", {
        method: "POST",
        body: JSON.stringify({
          title: request.payload?.title || `Yêu cầu ${request.code}`,
          request_type: request.type_code,
          description: request.payload?.reason || "",
          data: request.payload,
          amount: request.payload?.amount_vnd,
        }),
      });
      setSummary(res.data);
      setPhase(res.data?.fallback_used ? "fallback" : "done");
      if (res.data?.fallback_used) setError("AI không phản hồi. Phần hiển thị là tóm tắt dự phòng.");
      else notify("AI đã tạo tóm tắt thành công");
    } catch (e) {
      setError(`Không thể tóm tắt: ${errorText(e)}`);
      setPhase("error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="ai-panel">
      <button type="button" className="ai-btn" onClick={run} disabled={busy}>
        {busy ? "Đang tóm tắt…" : "AI tóm tắt hồ sơ"}
      </button>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {phase !== "idle" && <div className={`ai-progress-step ${phase}`} role="status"><span aria-hidden="true">{phase === "done" ? "✓" : ["error", "fallback"].includes(phase) ? "!" : "◌"}</span> {phase === "running" ? "Dịch vụ AI đang phân tích và tạo tóm tắt…" : phase === "done" ? "Đã hoàn thành tóm tắt" : phase === "fallback" ? "Dịch vụ AI không sẵn sàng — bản dự phòng" : "Tóm tắt chưa thành công"}</div>}
      {summary && (
        <>
          <p>
            <strong>{summary.summary}</strong>
          </p>
          {summary.key_points?.length > 0 && (
            <ul>
              {summary.key_points.map((pt) => (
                <li key={pt}>{pt}</li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
