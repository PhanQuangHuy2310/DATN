import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import { date, types } from "../domain.js";
import { Badge, useResource } from "./ui.jsx";
import { useDebounced } from "./design.jsx";

function useDismiss(open, setOpen) {
  const ref = useRef(null);
  useEffect(() => {
    if (!open) return undefined;
    const onDown = (event) => { if (ref.current && !ref.current.contains(event.target)) setOpen(false); };
    const onKey = (event) => { if (event.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("mousedown", onDown); document.removeEventListener("keydown", onKey); };
  }, [open, setOpen]);
  return ref;
}

/** Searches by request code or title. The endpoint applies the caller's own
 * read scope, so results are permission-aware by construction. */
export function GlobalSearch({ portal, onOpen }) {
  const [text, setText] = useState("");
  const [open, setOpen] = useState(false);
  const query = useDebounced(text.trim(), 300);
  const base = portal === "admin" ? "/api/v1/ops/requests" : "/api/v1/requests";
  const results = useResource(query.length >= 2 ? `${base}?limit=8&offset=0&q=${encodeURIComponent(query)}` : "");
  const ref = useDismiss(open, setOpen);
  const items = query.length >= 2 ? results.data?.items || [] : [];
  return <div className="ds-global-search" ref={ref} role="search">
    <label htmlFor="ds-global-search" className="sr-only">Tìm hồ sơ theo mã hoặc tiêu đề</label>
    <span aria-hidden="true">⌕</span>
    <input id="ds-global-search" type="search" role="combobox" aria-autocomplete="list" value={text} autoComplete="off" placeholder="Tìm mã hoặc tiêu đề hồ sơ…"
      aria-expanded={open && query.length >= 2} aria-controls="ds-global-search-results"
      onChange={(e) => { setText(e.target.value); setOpen(true); }} onFocus={() => setOpen(true)} />
    {open && query.length >= 2 && <ul id="ds-global-search-results" className="ds-search-results">
      {results.loading && !results.data && <li className="muted" style={{ padding: 8 }}>Đang tìm…</li>}
      {items.map((item) => <li key={item.id}><button type="button" onClick={() => { setOpen(false); setText(""); onOpen(item.id, item); }}>
        <span><strong>{item.code}</strong> <small>{item.type_name || types[item.type_code] || "Yêu cầu"}</small></span>
        <Badge value={item.status} />
      </button></li>)}
      {!results.loading && !items.length && <li className="muted" style={{ padding: 8 }}>Không tìm thấy hồ sơ trong phạm vi bạn được xem.</li>}
    </ul>}
  </div>;
}

export function NotificationBell({ onOpen, onViewAll }) {
  const [open, setOpen] = useState(false);
  const feed = useResource("/api/v1/notifications?limit=6&offset=0");
  const ref = useDismiss(open, setOpen);
  const unread = Number(feed.data?.unread_count) || 0;
  async function openItem(item) {
    setOpen(false);
    if (!item.read_at) {
      // Silent: the bell refreshes itself; no global toast for a read receipt.
      await api(`/api/v1/notifications/${item.id}/read`, { method: "POST", silent: true }).catch(() => {});
      feed.reload();
    }
    if (item.request_id) onOpen(item.request_id);
  }
  return <div className="client-notifications-anchor" ref={ref} style={{ position: "relative" }}>
    <button type="button" className="secondary ds-icon-button" onClick={() => setOpen((v) => !v)} aria-expanded={open}
      aria-label={unread ? `Thông báo, ${unread} chưa đọc` : "Thông báo"} title="Thông báo">
      <svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 8-3 9h18c0-1-3-2-3-9" /><path d="M10 21h4" /></svg>
      {unread > 0 && <span className="ds-count-badge">{unread > 99 ? "99+" : unread}</span>}
    </button>
    {open && <div className="ds-popover" role="region" aria-label="Thông báo mới">
      <div className="section-head" style={{ marginBottom: 0 }}><strong>Thông báo</strong><small className="muted">{unread} chưa đọc</small></div>
      <ul>{(feed.data?.items || []).map((item) => <li key={item.id} className={item.read_at ? "" : "is-unread"}>
        <button type="button" onClick={() => openItem(item)}><span>{item.label}</span><small className="muted">{date(item.created_at)}</small></button>
      </li>)}</ul>
      {!feed.data?.items?.length && <p className="muted">Chưa có thông báo.</p>}
      <button type="button" className="secondary" style={{ width: "100%" }} onClick={() => { setOpen(false); onViewAll(); }}>Xem tất cả thông báo</button>
    </div>}
  </div>;
}
