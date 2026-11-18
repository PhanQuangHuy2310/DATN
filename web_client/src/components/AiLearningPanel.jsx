import { useEffect, useState } from "react";
import { api } from "../api.js";
import { date } from "../domain.js";
import BadCasePanel from "./BadCasePanel.jsx";

const KIND_TEXT = {
  AUTO_APPROVE_REVOKED: "Thu hồi tự duyệt",
  ESCALATION_UNNECESSARY: "Chuyển luồng nhầm",
  RANKING_OVERRIDDEN: "Chọn người khác AI",
  REMEDIATION_DISMISSED: "Bỏ qua đề xuất",
};

function ClauseCard({ item, canUpdate, onDone }) {
  const initial = JSON.stringify(
    (item.suggestion?.rules || []).map(({ clause: _clause, ...rule }) => rule),
    null,
    2,
  );
  const [text, setText] = useState(initial === "[]" ? '[\n  {"request_type": null, "auto_approve": false, "min_risk": 4}\n]' : initial);
  const [error, setError] = useState("");

  async function decide(kind) {
    setError("");
    try {
      if (kind === "approve") {
        await api(`/api/v1/admin/regulations/clause-reviews/${item.id}/approve`, {
          method: "POST",
          body: JSON.stringify({ rules: JSON.parse(text), note: "Duyệt cách hiểu cho AI" }),
        });
      } else {
        const note = window.prompt("Lý do từ chối:");
        if (!note) return;
        await api(`/api/v1/admin/regulations/clause-reviews/${item.id}/reject`, {
          method: "POST",
          body: JSON.stringify({ note }),
        });
      }
      onDone();
    } catch (err) {
      setError(err?.message || "Không lưu được (kiểm tra JSON luật).");
    }
  }

  return (
    <li className="ai-learning-clause">
      <p>
        <strong>{item.regulation_code}</strong> · {date(item.created_at)}
      </p>
      <blockquote className="ai-citation-quote">{item.sentence}</blockquote>
      <p className="muted">AI chưa tự hiểu được: {item.reason}</p>
      <p className="muted">
        {item.suggestion?.rules?.length
          ? `Gemini đề xuất ${item.suggestion.rules.length} luật (đã qua kiểm tra bằng luật), bạn sửa nếu cần:`
          : `Gemini chưa đề xuất được${item.suggestion?.error ? ` (${item.suggestion.error})` : ""}; soạn luật thủ công:`}
      </p>
      <textarea
        className="ai-learning-json"
        rows={6}
        value={text}
        onChange={(e) => setText(e.target.value)}
        disabled={!canUpdate}
        aria-label="Luật dạng JSON"
      />
      {canUpdate && (
        <div className="ai-remedy-actions">
          <button type="button" onClick={() => decide("approve")}>
            Duyệt luật, AI học lại
          </button>
          <button type="button" className="secondary" onClick={() => decide("reject")}>
            Từ chối
          </button>
        </div>
      )}
      {error && <p role="alert">{error}</p>}
    </li>
  );
}

export default function AiLearningPanel({ canUpdate }) {
  const [clauses, setClauses] = useState(null);
  const [feedback, setFeedback] = useState(null);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    let alive = true;
    api("/api/v1/admin/regulations/clause-reviews?state=PENDING", { silent: true })
      .then((d) => alive && setClauses(d))
      .catch(() => alive && setClauses({ items: [] }));
    api("/api/v1/admin/ai-engine/feedback", { silent: true })
      .then((d) => alive && setFeedback(d))
      .catch(() => alive && setFeedback(null));
    return () => {
      alive = false;
    };
  }, [version]);

  useEffect(() => {
    if (feedback?.learning?.state !== "RUNNING") return undefined;
    const timer = setTimeout(() => setVersion((v) => v + 1), 5000);
    return () => clearTimeout(timer);
  }, [feedback]);

  async function learn() {
    await api("/api/v1/admin/ai-engine/feedback/learn", { method: "POST", body: "{}" });
    setVersion((v) => v + 1);
  }

  const summary = feedback?.summary;
  const result = feedback?.learning?.result;
  return (
    <section className="ai-remedy ai-learning" aria-label="AI học từ phản hồi">
      <h2>AI học từ phản hồi</h2>
      <p className="muted">
        Mỗi lần người sửa quyết định của AI được ghi nhớ và dùng ngay ở hồ sơ tương tự (cùng người, cùng loại);
        định kỳ AI học dồn và chỉ thay mô hình khi không kém mô hình cũ.
      </p>

      <BadCasePanel canUpdate={canUpdate} />

      <h3>Câu quy định chờ duyệt cách hiểu ({clauses?.items?.length ?? "…"})</h3>
      {clauses?.items?.length ? (
        <ol className="ai-remedy-items">
          {clauses.items.map((item) => (
            <ClauseCard key={item.id} item={item} canUpdate={canUpdate} onDone={() => setVersion((v) => v + 1)} />
          ))}
        </ol>
      ) : (
        <p className="muted">Không có câu nào chờ duyệt.</p>
      )}

      {summary?.installed && (
        <>
          <h3>Phản hồi đã ghi nhận</h3>
          <ul className="ai-escalation-causes">
            {Object.entries(summary.kinds || {}).map(([kind, v]) => (
              <li key={kind}>
                {KIND_TEXT[kind] || kind}: {v.active} ca đang dùng / {v.total}
              </li>
            ))}
          </ul>
          {summary.threshold_suggestions?.length > 0 && (
            <>
              <h3>Đề xuất chỉnh ngưỡng</h3>
              <ul className="ai-escalation-causes">
                {summary.threshold_suggestions.map((s) => (
                  <li key={s.code}>{s.text}</li>
                ))}
              </ul>
            </>
          )}
          <div className="ai-remedy-actions">
            <button type="button" onClick={learn} disabled={!canUpdate || feedback?.learning?.state === "RUNNING"}>
              {feedback?.learning?.state === "RUNNING" ? "AI đang học dồn…" : "Học dồn ngay"}
            </button>
          </div>
          {result && (
            <p role="status">
              Lần học gần nhất: <strong>{result.status}</strong>
              {result.version ? ` · phiên bản ${result.version}` : ""}
              {result.before
                ? ` · top-1 tập kiểm tra ${result.before.test_top1} → ${result.after?.test_top1}`
                : ""}
              {result.reasons?.length ? ` · giữ mô hình cũ: ${result.reasons.join("; ")}` : ""}
              {result.message ? ` · ${result.message}` : ""}
            </p>
          )}
        </>
      )}
    </section>
  );
}
