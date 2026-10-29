import { useState } from "react";
import { api } from "../api.js";
import { errorText } from "../domain.js";

function riskLevel(score) {
  if (score <= 2) return "low";
  if (score <= 3) return "medium";
  return "high";
}

function mapPredictedType(predicted) {
  const pred = String(predicted || "").toUpperCase();
  if (pred.includes("LEAVE")) return "LEAVE";
  if (["ACCESS", "VPN", "PERMISSION"].some((k) => pred.includes(k)))
    return "ACCESS";
  if (["EQUIPMENT", "DEVICE"].some((k) => pred.includes(k))) return "EQUIPMENT";
  return null;
}

function riskPayload(type, amount) {
  return {
    request_type: type.toLowerCase(),
    lifecycle_template: type === "EQUIPMENT" ? "B" : "A",
    risk_weight: type === "EQUIPMENT" ? 3 : 2,
    amount_vnd: amount,
  };
}

/**
 * AI hỗ trợ khi soạn hồ sơ: gợi ý phân loại + dự đoán rủi ro.
 * Chỉ mang tính tham khảo; không tự phê duyệt (AI auto-approve ngoài P0).
 */
export function AiRequestAssist({ type, getValues, onSuggestType }) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [classify, setClassify] = useState(null),
    [risk, setRisk] = useState(null);

  async function run() {
    const { title = "", reason = "", amount_vnd: amount = 0 } = getValues();
    if (!String(title).trim()) {
      setError("Vui lòng nhập tiêu đề trước khi yêu cầu AI gợi ý.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const [c, r] = await Promise.all([
        api("/api/v1/ai/classify", {
          method: "POST",
          body: JSON.stringify({ title, description: reason }),
        }),
        api("/api/v1/ai/risk-score", {
          method: "POST",
          body: JSON.stringify(riskPayload(type, Number(amount) || 0)),
        }),
      ]);
      setClassify(c.data);
      setRisk(r.data);
      const suggested = mapPredictedType(c.data?.predicted_request_type);
      if (suggested && suggested !== type) onSuggestType?.(suggested);
    } catch (e) {
      setError(`AI tạm thời không khả dụng: ${errorText(e)}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="ai-panel">
      <div className="section-head">
        <h3>Trợ lý AI</h3>
        <button type="button" className="ai-btn" onClick={run} disabled={busy}>
          {busy ? "AI đang xử lý…" : "Gợi ý & đánh giá rủi ro"}
        </button>
      </div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {classify && (
        <p>
          Loại đề xuất: <strong>{classify.predicted_request_type}</strong> (độ
          tin cậy{" "}
          {Math.round((classify.confidence_request_type || 0) * 100)}%) · Phòng
          ban: <strong>{classify.predicted_department}</strong>
          {classify.workflow_suggestion && (
            <>
              <br />
              <em>Gợi ý: {classify.workflow_suggestion}</em>
            </>
          )}
        </p>
      )}
      {risk && (
        <p>
          Điểm rủi ro:{" "}
          <span className={`badge badge-${riskLevel(risk.risk_score)}`}>
            {risk.risk_score}/5 ({risk.risk_label})
          </span>{" "}
          · Đủ điều kiện duyệt nhanh:{" "}
          <strong>{risk.auto_approve_eligible ? "Có" : "Không"}</strong>
        </p>
      )}
    </div>
  );
}

/** AI tóm tắt nội dung hồ sơ cho người xử lý. */
export function AiSummary({ request }) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [summary, setSummary] = useState(null);

  async function run() {
    setBusy(true);
    setError("");
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
    } catch (e) {
      setError(`Không thể tóm tắt: ${errorText(e)}`);
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
