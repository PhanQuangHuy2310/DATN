import { useEffect, useState } from "react";
import { api } from "../api.js";
import { date } from "../domain.js";

const VERDICT_TEXT = {
  EXISTING_SCOPE: "Mở rộng bad case có sẵn sang loại đơn khác",
  NEW_PATTERN: "Kiểu rủi ro mới",
  ONE_OFF: "Lý do riêng của hồ sơ",
};
const STATE_TEXT = { CANDIDATE: "Chờ admin", ACTIVE: "Đang dùng", REJECTED: "Không tạo", RETIRED: "Đã ngưng" };
const SOURCE_TEXT = { CATALOG: "Có sẵn", AI: "AI tự học", ADMIN: "Admin tạo" };
const FILTERS = [
  ["CANDIDATE", "Chờ admin"],
  ["ACTIVE", "Đang dùng"],
  ["REJECTED", "Không tạo"],
  ["RETIRED", "Đã ngưng"],
];

function Criteria({ evaluation }) {
  if (!evaluation?.criteria?.length) return null;
  return (
    <ul className="bad-case-criteria">
      {evaluation.criteria.map((c) => (
        <li key={c.key} className={c.ok ? "ok" : "missing"}>
          <span aria-hidden="true">{c.ok ? "✓" : "✗"}</span> {c.text}
        </li>
      ))}
    </ul>
  );
}

function Evidence({ items }) {
  if (!items?.length) return null;
  return (
    <details className="bad-case-evidence">
      <summary>Lý do người duyệt đã nêu ({items.length} gần nhất)</summary>
      <ul>
        {items.map((e, i) => (
          <li key={i}>
            <blockquote className="ai-citation-quote">{e.reason}</blockquote>
            <span className="muted">
              {e.approver || "Người duyệt"} · {e.request_code} · {date(e.created_at)}
              {e.confidence != null ? ` · AI chắc ${Math.round(e.confidence * 100)}%` : ""}
            </span>
            {e.why_missed && <p className="muted">Vì sao AI bỏ sót: {e.why_missed}</p>}
          </li>
        ))}
      </ul>
    </details>
  );
}

function CaseCard({ item, canUpdate, onDone }) {
  const [condition, setCondition] = useState(item.condition ? JSON.stringify(item.condition, null, 2) : "");
  const [title, setTitle] = useState(item.title);
  const [rationale, setRationale] = useState(item.rationale);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const ev = item.evaluation || {};

  async function decide(decision) {
    setError("");
    const body = {};
    if (decision === "approve") {
      body.title = title;
      body.rationale = rationale;
      if (item.detector === "RULE") {
        try {
          body.condition = condition.trim() ? JSON.parse(condition) : null;
        } catch {
          setError("Điều kiện không đúng JSON.");
          return;
        }
      }
      body.note = "Admin xác nhận tạo bad case";
    } else {
      const note = window.prompt(
        decision === "reject" ? "Vì sao không tạo bad case này?" : decision === "retire" ? "Vì sao ngưng?" : "Ghi chú (không bắt buộc):",
      );
      if (note === null) return;
      if (decision !== "enable" && note.trim().length < 5) return;
      body.note = note;
    }
    setBusy(true);
    try {
      await api(`/api/v1/admin/ai-engine/bad-cases/${item.id}/${decision}`, {
        method: "POST",
        body: JSON.stringify(body),
      });
      onDone();
    } catch (err) {
      setError(err?.message || "Không lưu được.");
    } finally {
      setBusy(false);
    }
  }

  const candidate = item.state === "CANDIDATE";
  return (
    <li className={`bad-case-card state-${item.state.toLowerCase()}`}>
      <div className="ai-remedy-item-head">
        <strong>{item.title}</strong>
        <span className="muted">
          <code>{item.code}</code> · {SOURCE_TEXT[item.source] || item.source} · {STATE_TEXT[item.state]}
          {item.verdict ? ` · ${VERDICT_TEXT[item.verdict] || item.verdict}` : ""}
        </span>
      </div>
      <p className="muted">
        Loại đơn: {item.request_types.join(", ")} · khi dính thì chuyển sang quy trình {item.escalate_to} · rủi ro{" "}
        {item.risk}/5 · {item.evidence_count} lần thu hồi liên quan
      </p>
      <p>
        <strong>Vì sao là bad case:</strong> {item.rationale}
      </p>
      {item.condition_text && (
        <p>
          <strong>AI nhận ra khi:</strong> {item.condition_text}
        </p>
      )}
      {ev.summary && (
        <p className={ev.enough ? "bad-case-verdict ok" : "bad-case-verdict"}>
          <strong>AI đánh giá:</strong> {ev.summary}
        </p>
      )}
      <Criteria evaluation={ev} />
      <Evidence items={item.evidence} />
      {candidate && ev.question && (
        <p className="bad-case-question">
          <strong>AI hỏi:</strong> {ev.question}
        </p>
      )}
      {candidate && canUpdate && (
        <div className="bad-case-edit">
          <label>
            Tên bad case
            <input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} />
          </label>
          <label>
            Vì sao là bad case
            <textarea rows={2} value={rationale} onChange={(e) => setRationale(e.target.value)} maxLength={2000} />
          </label>
          {item.detector === "RULE" && (
            <label>
              Điều kiện để AI tự nhận ra (JSON)
              <textarea
                className="ai-learning-json"
                rows={4}
                value={condition}
                placeholder='{"all": [{"feature": "notice_hours", "op": "<=", "value": 12}]}'
                onChange={(e) => setCondition(e.target.value)}
              />
            </label>
          )}
        </div>
      )}
      {canUpdate && (
        <div className="ai-remedy-actions">
          {candidate && (
            <>
              <button type="button" onClick={() => decide("approve")} disabled={busy}>
                Có, tạo bad case
              </button>
              <button type="button" className="secondary" onClick={() => decide("reject")} disabled={busy}>
                Không tạo
              </button>
            </>
          )}
          {item.state === "ACTIVE" && (
            <button type="button" className="secondary" onClick={() => decide("retire")} disabled={busy}>
              Ngưng dùng
            </button>
          )}
          {item.state === "RETIRED" && (
            <button type="button" className="secondary" onClick={() => decide("enable")} disabled={busy}>
              Bật lại
            </button>
          )}
        </div>
      )}
      {error && <p role="alert">{error}</p>}
    </li>
  );
}

export default function BadCasePanel({ canUpdate }) {
  const [data, setData] = useState(null);
  const [filter, setFilter] = useState("CANDIDATE");
  const [version, setVersion] = useState(0);

  useEffect(() => {
    let alive = true;
    api("/api/v1/admin/ai-engine/bad-cases?state=ALL", { silent: true })
      .then((d) => alive && setData(d))
      .catch(() => alive && setData({ items: [], installed: false }));
    return () => {
      alive = false;
    };
  }, [version]);

  if (!data) return <p className="muted">Đang tải danh mục bad case…</p>;
  if (!data.installed) return <p className="muted">Chưa chạy migration 25 (bảng bad case).</p>;
  const counts = Object.fromEntries(FILTERS.map(([k]) => [k, data.items.filter((i) => i.state === k).length]));
  const items = data.items.filter((i) => i.state === filter);
  const t = data.thresholds || {};
  return (
    <section className="bad-case-panel" aria-label="Danh mục bad case">
      <h3>Danh mục bad case</h3>
      <p className="muted">
        Khi người duyệt thu hồi hồ sơ AI đã tự duyệt, AI đọc lý do và xếp vào: bad case có sẵn (AI bỏ sót), kiểu
        rủi ro mới, hoặc lý do riêng của hồ sơ. Kiểu mới xảy ra từ {t.min_evidence} lần trong {t.window_days} ngày,
        ở từ {t.min_requesters} người gửi, được {t.min_approvers} người duyệt nêu, đo được bằng dữ liệu và bắt không
        quá {Math.round((t.max_coverage || 0) * 100)}% hồ sơ cùng loại thì AI tự thêm vào danh mục; chưa đủ thì AI
        nêu lý do và hỏi admin.
      </p>
      <div className="bad-case-filters" role="tablist">
        {FILTERS.map(([key, label]) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={filter === key}
            className={filter === key ? "" : "secondary"}
            onClick={() => setFilter(key)}
          >
            {label} ({counts[key]})
          </button>
        ))}
      </div>
      {items.length ? (
        <ol className="ai-remedy-items">
          {items.map((item) => (
            <CaseCard key={`${item.id}-${item.updated_at}`} item={item} canUpdate={canUpdate} onDone={() => setVersion((v) => v + 1)} />
          ))}
        </ol>
      ) : (
        <p className="muted">Không có bad case nào ở mục này.</p>
      )}
    </section>
  );
}
