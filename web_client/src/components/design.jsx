/** Shared design-system primitives for both portals (see design-system.css). */
import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { date } from "../domain.js";
import { ActionForm, Badge } from "./ui.jsx";

/** Explanatory copy behind an (i) button: shown on hover, keyboard focus or
 * tap, and always announced to screen readers through aria-describedby. */
export function InfoHint({ children, label = "Giải thích" }) {
  const [open, setOpen] = useState(false);
  const [flip, setFlip] = useState(false);
  const id = useId();
  const ref = useRef(null);
  useEffect(() => {
    if (!open) return undefined;
    const onDown = (event) => { if (!ref.current?.contains(event.target)) setOpen(false); };
    const onKey = (event) => { if (event.key === "Escape") setOpen(false); };
    document.addEventListener("pointerdown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);
  if (!children) return null;
  // Open toward the side with room, so a hint near the right edge never
  // pushes the page wider than the viewport.
  const place = () => {
    const left = ref.current?.getBoundingClientRect().left ?? 0;
    setFlip(left + 380 > window.innerWidth);
  };
  return (
    <span className={`ds-info${open ? " is-open" : ""}${flip ? " is-flip" : ""}`} ref={ref}
      onPointerEnter={place} onFocus={place}>
      <button type="button" className="ds-info-button" aria-label={label} aria-describedby={id}
        aria-expanded={open} onClick={() => setOpen((v) => !v)}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
          strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <circle cx="12" cy="12" r="9" /><path d="M12 11v5" /><path d="M12 8h.01" />
        </svg>
      </button>
      <span className="ds-info-pop" role="tooltip" id={id}>{children}</span>
    </span>
  );
}

/** Page description: on the page's first heading it moves next to the page
 * title in the top bar; anywhere else it stays inline as an InfoHint. */
export function PageInfo({ children }) {
  const ref = useRef(null);
  const [slot, setSlot] = useState(null);
  useEffect(() => {
    const heading = ref.current?.closest(".page-heading");
    const first = document.querySelector("main#main .page-heading:not(.ds-detail-header)");
    setSlot(heading && heading === first ? document.getElementById("page-title-info") : null);
  }, [children]);
  if (!children) return null;
  const hint = <InfoHint label="Về trang này">{children}</InfoHint>;
  return <span ref={ref} className="ds-page-info">{slot ? createPortal(hint, slot) : hint}</span>;
}

export function PageHeader({ eyebrow, title, description, note, action }) {
  return (
    <div className="page-heading ds-page-header">
      <div className="ds-page-header-text">
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1>{title}{(description || note) && <PageInfo>
          {description && <span className="ds-info-line">{description}</span>}
          {note && <span className="ds-info-line">{note}</span>}
        </PageInfo>}</h1>
      </div>
      {action && <div className="ds-page-header-actions">{action}</div>}
    </div>
  );
}

export function PageTabs({ tabs, value, onChange, label }) {
  return (
    <div className="ds-tabs" role="tablist" aria-label={label}>
      {tabs.map(([key, title, count]) => (
        <button
          key={key}
          type="button"
          role="tab"
          aria-selected={value === key}
          className={value === key ? "ds-tab is-active" : "ds-tab"}
          onClick={() => onChange(key)}
        >
          {title}
          {count != null && <span className="ds-tab-count">{count}</span>}
        </button>
      ))}
    </div>
  );
}

export function StatCard({ title, value, detail, tone }) {
  return (
    <article className={`panel ds-stat ${tone ? `ds-stat-${tone}` : ""}`}>
      <span className="ds-stat-title">{title}</span>
      <strong className="ds-stat-value">{value ?? "—"}</strong>
      {detail && <small className="ds-stat-detail">{detail}</small>}
    </article>
  );
}

export const StatusBadge = Badge;

export function EmptyState({ title, description, action }) {
  return (
    <div className="ds-empty" role="status">
      <span className="ds-empty-icon" aria-hidden="true">
        ◌
      </span>
      <strong>{title}</strong>
      {description && <p className="muted">{description}</p>}
      {action}
    </div>
  );
}

export function Skeleton({ rows = 3 }) {
  return (
    <div className="ds-skeleton" aria-hidden="true">
      {Array.from({ length: rows }, (_, i) => (
        <span
          key={i}
          className="ds-skeleton-line"
          style={{ width: `${92 - (i % 3) * 14}%` }}
        />
      ))}
    </div>
  );
}

export function CardGridSkeleton({ count = 6 }) {
  return (
    <div className="ds-skeleton-card-grid" aria-hidden="true">
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="panel ds-skeleton-card">
          <span className="ds-skeleton-line" style={{ width: "38%", height: "10px" }} />
          <span className="ds-skeleton-line" style={{ width: "76%", height: "16px" }} />
          <span className="ds-skeleton-line" style={{ width: "92%" }} />
          <span className="ds-skeleton-line" style={{ width: "64%" }} />
        </div>
      ))}
    </div>
  );
}

export function TableSkeleton({ rows = 5, cols = 6 }) {
  return (
    <div className="ds-skeleton-table" aria-hidden="true">
      <div className="ds-skeleton-table-head">
        {Array.from({ length: cols }, (_, c) => (
          <span key={c} className="ds-skeleton-line" style={{ width: "75%", height: "10px" }} />
        ))}
      </div>
      {Array.from({ length: rows }, (_, r) => (
        <div key={r} className="ds-skeleton-table-row">
          {Array.from({ length: cols }, (_, c) => (
            <span
              key={c}
              className="ds-skeleton-line"
              style={{ width: `${85 - ((r + c) % 3) * 15}%` }}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

export function DetailSkeleton() {
  return (
    <div className="ds-skeleton-detail" aria-hidden="true">
      <div className="panel ds-skeleton-card">
        <span className="ds-skeleton-line" style={{ width: "25%", height: "10px" }} />
        <span className="ds-skeleton-line" style={{ width: "55%", height: "22px" }} />
        <span className="ds-skeleton-line" style={{ width: "40%" }} />
      </div>
      <div className="ds-skeleton-card-grid">
        {Array.from({ length: 4 }, (_, i) => (
          <div key={i} className="panel ds-skeleton-card">
            <span className="ds-skeleton-line" style={{ width: "45%", height: "10px" }} />
            <span className="ds-skeleton-line" style={{ width: "80%", height: "15px" }} />
          </div>
        ))}
      </div>
    </div>
  );
}

export function ShellSkeleton() {
  return (
    <main className="ds-shell-skeleton" aria-busy="true" aria-live="polite">
      <span className="sr-only">Đang tải không gian làm việc EAS…</span>
      <div className="ds-shell-skeleton-sidebar" aria-hidden="true">
        <span className="ds-skeleton-line" style={{ width: "70%", height: "24px", opacity: 0.25 }} />
        {Array.from({ length: 5 }, (_, i) => (
          <span key={i} className="ds-skeleton-line" style={{ width: "85%", height: "34px", opacity: 0.16 }} />
        ))}
      </div>
      <div className="ds-shell-skeleton-main" aria-hidden="true">
        <div className="ds-shell-skeleton-topbar">
          <span className="ds-skeleton-line" style={{ width: "180px", height: "18px" }} />
          <span className="ds-skeleton-line" style={{ width: "260px", height: "32px" }} />
        </div>
        <div className="ds-shell-skeleton-body">
          <CardGridSkeleton count={4} />
          <TableSkeleton rows={4} cols={5} />
        </div>
      </div>
    </main>
  );
}

/** Confirmation for destructive or irreversible actions. `onConfirm` may throw;
 * the error is shown inside the dialog and the dialog stays open. */
export function ConfirmDialog({
  title,
  message,
  warningNote = "",
  confirmLabel = "Xác nhận",
  danger = false,
  onConfirm,
  onClose,
  children,
}) {
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current;
    el.showModal();
    return () => el.close();
  }, []);
  const effectiveWarning =
    danger && !warningNote
      ? "Lưu ý: Thao tác này không thể hoàn tác sau khi xác nhận."
      : warningNote;
  return (
    <dialog ref={ref} onCancel={onClose} aria-label={title} className="ds-confirm">
      <div className="section-head">
        <h2>{title}</h2>
        <button
          type="button"
          className="secondary"
          onClick={onClose}
          aria-label="Đóng hộp thoại"
        >
          ×
        </button>
      </div>
      {message && <p>{message}</p>}
      <ActionForm
        submitLabel={confirmLabel}
        danger={danger}
        warningNote={effectiveWarning}
        onSubmit={onConfirm}
      >
        {children}
      </ActionForm>
      <button type="button" className="secondary ds-confirm-cancel" onClick={onClose}>
        Hủy
      </button>
    </dialog>
  );
}

/** Vertical timeline; each item: {key, title, meta, state: done|current|upcoming|failed|skipped, children}. */
export function WorkflowTimeline({ items }) {
  return (
    <ol className="ds-timeline">
      {items.map((item) => (
        <li key={item.key} className={`ds-timeline-item is-${item.state || "upcoming"}`}>
          <span className="ds-timeline-dot" aria-hidden="true">
            {item.state === "done"
              ? "✓"
              : item.state === "failed"
                ? "!"
                : item.state === "skipped"
                  ? "—"
                  : ""}
          </span>
          <div className="ds-timeline-body">
            <strong>{item.title}</strong>
            {item.meta && <small className="muted">{item.meta}</small>}
            {item.children}
          </div>
        </li>
      ))}
    </ol>
  );
}

export function SearchInput({ value, onChange, placeholder, label = "Tìm kiếm" }) {
  return (
    <label className="ds-search">
      <span className="sr-only">{label}</span>
      <span aria-hidden="true">⌕</span>
      <input
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
      />
    </label>
  );
}

/** Debounced value for search boxes. */
export function useDebounced(value, delay = 300) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}

export function DateTimeText({ value, empty = "—" }) {
  return value ? <time dateTime={value}>{date(value)}</time> : <span className="muted">{empty}</span>;
}
