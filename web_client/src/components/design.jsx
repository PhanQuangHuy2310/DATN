/** Shared design-system primitives for both portals (see design-system.css). */
import { useEffect, useRef, useState } from "react";
import { date } from "../domain.js";
import { ActionForm, Badge } from "./ui.jsx";

export function PageHeader({ eyebrow, title, description, action }) {
  return <div className="page-heading ds-page-header">
    <div className="ds-page-header-text">
      {eyebrow && <p className="eyebrow">{eyebrow}</p>}
      <h1>{title}</h1>
      {description && <p className="muted">{description}</p>}
    </div>
    {action && <div className="ds-page-header-actions">{action}</div>}
  </div>;
}

export function PageTabs({ tabs, value, onChange, label }) {
  return <div className="ds-tabs" role="tablist" aria-label={label}>
    {tabs.map(([key, title, count]) => <button key={key} type="button" role="tab" aria-selected={value === key}
      className={value === key ? "ds-tab is-active" : "ds-tab"} onClick={() => onChange(key)}>
      {title}{count != null && <span className="ds-tab-count">{count}</span>}
    </button>)}
  </div>;
}

export function StatCard({ title, value, detail, tone }) {
  return <article className={`panel ds-stat ${tone ? `ds-stat-${tone}` : ""}`}>
    <span className="ds-stat-title">{title}</span>
    <strong className="ds-stat-value">{value ?? "—"}</strong>
    {detail && <small className="ds-stat-detail">{detail}</small>}
  </article>;
}

export const StatusBadge = Badge;

export function EmptyState({ title, description, action }) {
  return <div className="ds-empty" role="status">
    <span className="ds-empty-icon" aria-hidden="true">◌</span>
    <strong>{title}</strong>
    {description && <p className="muted">{description}</p>}
    {action}
  </div>;
}

export function Skeleton({ rows = 3 }) {
  return <div className="ds-skeleton" aria-hidden="true">
    {Array.from({ length: rows }, (_, i) => <span key={i} className="ds-skeleton-line" style={{ width: `${92 - (i % 3) * 14}%` }} />)}
  </div>;
}

/** Confirmation for destructive or irreversible actions. `onConfirm` may throw;
 * the error is shown inside the dialog and the dialog stays open. */
export function ConfirmDialog({ title, message, confirmLabel = "Xác nhận", danger = false, onConfirm, onClose, children }) {
  const ref = useRef(null);
  useEffect(() => { const el = ref.current; el.showModal(); return () => el.close(); }, []);
  return <dialog ref={ref} onCancel={onClose} aria-label={title} className="ds-confirm">
    <div className="section-head"><h2>{title}</h2>
      <button type="button" className="secondary" onClick={onClose} aria-label="Đóng hộp thoại">×</button></div>
    {message && <p>{message}</p>}
    <ActionForm submitLabel={confirmLabel} danger={danger} onSubmit={onConfirm}>{children}</ActionForm>
    <button type="button" className="secondary ds-confirm-cancel" onClick={onClose}>Hủy</button>
  </dialog>;
}

/** Vertical timeline; each item: {key, title, meta, state: done|current|upcoming|failed|skipped, children}. */
export function WorkflowTimeline({ items }) {
  return <ol className="ds-timeline">
    {items.map((item) => <li key={item.key} className={`ds-timeline-item is-${item.state || "upcoming"}`}>
      <span className="ds-timeline-dot" aria-hidden="true">{item.state === "done" ? "✓" : item.state === "failed" ? "!" : item.state === "skipped" ? "—" : ""}</span>
      <div className="ds-timeline-body">
        <strong>{item.title}</strong>
        {item.meta && <small className="muted">{item.meta}</small>}
        {item.children}
      </div>
    </li>)}
  </ol>;
}

export function SearchInput({ value, onChange, placeholder, label = "Tìm kiếm" }) {
  return <label className="ds-search"><span className="sr-only">{label}</span>
    <span aria-hidden="true">⌕</span>
    <input type="search" value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} />
  </label>;
}

/** Debounced value for search boxes. */
export function useDebounced(value, delay = 300) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => { const t = setTimeout(() => setDebounced(value), delay); return () => clearTimeout(t); }, [value, delay]);
  return debounced;
}

export function DateTimeText({ value, empty = "—" }) {
  return value ? <time dateTime={value}>{date(value)}</time> : <span className="muted">{empty}</span>;
}
