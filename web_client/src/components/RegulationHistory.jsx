import { useEffect, useState } from "react";
import { api } from "../api.js";
import { errorText } from "../domain.js";
import { ACTION_LABELS, lineDiff } from "../regulationImport.js";

function Diff({ item }) {
  if (item.action_type === "CREATE" || item.previous_content == null) {
    return <pre className="reg-diff">{item.content}</pre>;
  }
  if (item.action_type === "DELETE_MAJOR" && item.previous_content === item.content) {
    return <pre className="reg-diff del-all">{item.content}</pre>;
  }
  const lines = lineDiff(item.previous_content, item.content);
  if (!lines.some((l) => l.kind !== "same")) {
    return <p className="reg-history-note">Nội dung không đổi (chỉ đổi tiêu đề, danh mục hoặc bật lại quy định).</p>;
  }
  return (
    <pre className="reg-diff">
      {lines.map((l, i) => (
        <span key={i} className={`reg-diff-${l.kind}`}>
          {l.kind === "add" ? "+ " : l.kind === "del" ? "− " : "  "}
          {l.text}
          {"\n"}
        </span>
      ))}
    </pre>
  );
}

/** Lịch sử mọi lần thêm / sửa / gỡ quy định, kể cả quy định đã gỡ; bấm từng bản để xem đã đổi gì. */
export default function RegulationHistory({ apiBase, onClose, initialCode = "" }) {
  const [code, setCode] = useState(initialCode);
  const [query, setQuery] = useState("");
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [open, setOpen] = useState(null);

  useEffect(() => {
    let alive = true;
    const timer = setTimeout(async () => {
      try {
        const params = new URLSearchParams({ code, q: query.trim() });
        const res = await api(`${apiBase}/regulations/history?${params}`, { silent: true });
        if (alive) {
          setData(res);
          setError("");
        }
      } catch (err) {
        if (alive) setError(errorText(err));
      }
    }, 250);
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [apiBase, code, query]);

  return (
    <div className="eas-modal-overlay">
      <div className="eas-modal-card view-modal reg-history-modal">
        <div className="eas-modal-header">
          <h3>Lịch sử thay đổi quy định</h3>
          <button type="button" className="eas-modal-close" onClick={onClose} aria-label="Đóng">✕</button>
        </div>
        <div className="eas-modal-body">
          <div className="reg-history-filters">
            <select className="eas-select" value={code} onChange={(e) => setCode(e.target.value)} aria-label="Lọc theo mã">
              <option value="">Tất cả quy định</option>
              {(data?.codes || []).map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
            <input className="eas-input" value={query} placeholder="Tìm theo mã, tiêu đề, nội dung"
              onChange={(e) => setQuery(e.target.value)} aria-label="Tìm trong lịch sử" />
          </div>
          {error && <p className="reg-history-note error">{error}</p>}
          {!data && !error && <p className="reg-history-note">Đang tải...</p>}
          {data && !data.items.length && <p className="reg-history-note">Chưa có thay đổi nào khớp bộ lọc.</p>}
          {data?.count >= data?.limit && (
            <p className="reg-history-note">Hiện {data.limit} bản gần nhất; lọc theo mã để xem bản cũ hơn.</p>
          )}
          <ol className="reg-history-list">
            {(data?.items || []).map((h) => (
              <li key={h.id} className={`reg-history-item action-${h.action_type}`}>
                <button type="button" className="reg-history-head" aria-expanded={open === h.id}
                  onClick={() => setOpen(open === h.id ? null : h.id)}>
                  <span className="timeline-badge">v{h.version_string}</span>
                  <span className="reg-history-action">{ACTION_LABELS[h.action_type] || h.action_type}</span>
                  <strong>{h.code || "(đã xóa hẳn)"}</strong>
                  <span className="reg-history-title">{h.title}</span>
                  {h.regulation_deleted && <span className="reg-history-gone">đã gỡ</span>}
                  <span className="timeline-time">
                    {h.created_at ? new Date(h.created_at).toLocaleString("vi-VN") : ""} · {h.created_by}
                  </span>
                </button>
                {open === h.id && (
                  <div className="reg-history-body">
                    {h.change_summary && <p className="timeline-summary">{h.change_summary}</p>}
                    {h.previous_title && h.previous_title !== h.title && (
                      <p className="reg-history-note">Tiêu đề: «{h.previous_title}» → «{h.title}»</p>
                    )}
                    <Diff item={h} />
                  </div>
                )}
              </li>
            ))}
          </ol>
        </div>
        <div className="eas-modal-actions">
          <button type="button" className="btn-secondary" onClick={onClose}>Đóng</button>
        </div>
      </div>
    </div>
  );
}
