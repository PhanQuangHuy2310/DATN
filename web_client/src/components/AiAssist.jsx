import { useState } from "react";
import { api, notify } from "../api.js";
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
 * Hỗ trợ nội dung và phân tích rủi ro; không thay quyết định của người duyệt.
 */
export function AiRequestAssist({ type, getValues, onSuggestType }) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [classify, setClassify] = useState(null),
    [risk, setRisk] = useState(null),
    [steps, setSteps] = useState({});

  async function run() {
    const { title = "", reason = "", amount_vnd: amount = 0 } = getValues();
    if (!String(title).trim()) {
      setError("Vui lòng nhập tiêu đề trước khi yêu cầu AI gợi ý.");
      return;
    }
    setBusy(true);
    setError("");
    setClassify(null);
    setRisk(null);
    setSteps({ classify: "running", risk: "running" });
    const tasks = await Promise.allSettled([
      api("/api/v1/ai/classify", {
        method: "POST", body: JSON.stringify({ title, description: reason }),
      }).then((response) => {
        setClassify(response.data);
        setSteps((prev) => ({ ...prev, classify: response.data?.fallback_used ? "fallback" : "done" }));
        const suggested = mapPredictedType(response.data?.predicted_request_type);
        if (suggested && suggested !== type) onSuggestType?.(suggested);
        return response;
      }).catch((error) => {
        setSteps((prev) => ({ ...prev, classify: "error" }));
        throw error;
      }),
      api("/api/v1/ai/risk-score", {
        method: "POST", body: JSON.stringify(riskPayload(type, Number(amount) || 0)),
      }).then((response) => {
        setRisk(response.data);
        setSteps((prev) => ({ ...prev, risk: response.data?.fallback_used ? "fallback" : "done" }));
        return response;
      }).catch((error) => {
        setSteps((prev) => ({ ...prev, risk: "error" }));
        throw error;
      }),
    ]);
    const rejected = tasks.filter((item) => item.status === "rejected");
    if (rejected.length) setError(`Một số phân tích chưa hoàn tất: ${errorText(rejected[0].reason)}`);
    else if (tasks.some((item) => item.value?.data?.fallback_used)) setError("AI chưa phản hồi đầy đủ; một phần kết quả là dữ liệu dự phòng, không phải kết quả mô hình.");
    else notify("AI đã hoàn thành phân loại và đánh giá rủi ro");
    setBusy(false);
  }

  return (
    <div className="ai-panel">
      <div className="section-head">
        <h3>Trợ lý AI</h3>
        <button type="button" className="ai-btn" onClick={run} disabled={busy}>
          {busy ? "AI đang xử lý…" : "Gợi ý & đánh giá rủi ro"}
        </button>
      </div>
      {Object.keys(steps).length > 0 && (
        <div className="ai-progress" aria-live="polite">
          {[["classify", "Phân loại nội dung"], ["risk", "Đánh giá rủi ro"]].map(([key, title]) => (
            <div className={`ai-progress-step ${steps[key]}`} key={key}>
              <span aria-hidden="true">{steps[key] === "done" ? "✓" : ["error", "fallback"].includes(steps[key]) ? "!" : "◌"}</span>
              <span>{title}</span><small>{steps[key] === "done" ? "Hoàn thành" : steps[key] === "error" ? "Không thành công" : steps[key] === "fallback" ? "Dữ liệu dự phòng" : "Đang xử lý…"}</small>
            </div>
          ))}
        </div>
      )}
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
