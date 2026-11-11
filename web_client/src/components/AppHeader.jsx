import { useEffect, useRef, useState } from "react";
import Icon from "./Icon.jsx";
import { api } from "../api.js";
import { date, types } from "../domain.js";
import { Badge, useResource } from "./ui.jsx";
import { useDebounced } from "./design.jsx";
import { formatNotificationLabel } from "./notificationLabels.js";

function useDismiss(open, setOpen) {
  const ref = useRef(null);
  useEffect(() => {
    if (!open) return undefined;
    const onDown = (event) => {
      if (ref.current && !ref.current.contains(event.target)) setOpen(false);
    };
    const onKey = (event) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, setOpen]);
  return ref;
}

const QUICK_FEATURES = [
  { key: "home", label: "Tổng quan", hint: "Chức năng", portal: "both" },
  { key: "request-catalog", label: "Yêu cầu & Quy trình", hint: "Chức năng", portal: "admin" },
  { key: "mine", label: "Yêu cầu của tôi", hint: "Chức năng", portal: "client" },
  { key: "approval", label: "Hộp việc phê duyệt", hint: "Chức năng", portal: "client" },
  { key: "execution", label: "Công việc thực hiện", hint: "Chức năng", portal: "client" },
  { key: "acceptance", label: "Nghiệm thu hồ sơ", hint: "Chức năng", portal: "client" },
  { key: "org-chart", label: "Sơ đồ công ty", hint: "Chức năng", portal: "admin" },
  { key: "org-client", label: "Sơ đồ công ty", hint: "Chức năng", portal: "client" },
  { key: "users", label: "Quản lý người dùng", hint: "Chức năng", portal: "admin" },
  { key: "permissions", label: "Ma trận phân quyền", hint: "Chức năng", portal: "admin" },
  { key: "policy", label: "Quy định", hint: "Chức năng", portal: "admin" },
  { key: "regulations-client", label: "Quy định nội bộ", hint: "Chức năng", portal: "client" },
  { key: "ai-process", label: "AI hỗ trợ & Đánh giá rủi ro", hint: "Chức năng", portal: "both" },
  { key: "api-admin", label: "Quản lý API", hint: "Chức năng", portal: "admin" },
  { key: "system", label: "Phiên bản hệ thống", hint: "Chức năng", portal: "admin" },
  { key: "profile", label: "Hồ sơ cá nhân & Đổi mật khẩu", hint: "Tài khoản", portal: "both" },
  { key: "delegation", label: "Ủy quyền phê duyệt", hint: "Nghiệp vụ", portal: "client" },
  { key: "notifications", label: "Trung tâm thông báo", hint: "Chức năng", portal: "both" },
];

/** Searches by request code, title, requester name or quick feature title. */
export function GlobalSearch({ portal, onOpen, onNavigate }) {
  const [text, setText] = useState("");
  const [open, setOpen] = useState(false);
  const query = useDebounced(text.trim(), 280);
  const base = portal === "admin" ? "/api/v1/ops/requests" : "/api/v1/requests";
  const results = useResource(
    query.length >= 2
      ? `${base}?limit=8&offset=0&q=${encodeURIComponent(query)}`
      : "",
  );
  const ref = useDismiss(open, setOpen);
  const items = query.length >= 2 ? results.data?.items || [] : [];

  const matchedFeatures =
    query.length >= 2
      ? QUICK_FEATURES.filter(
          (f) =>
            (f.portal === "both" || f.portal === portal) &&
            f.label.toLocaleLowerCase("vi-VN").includes(query.toLocaleLowerCase("vi-VN")),
        )
      : [];

  return (
    <div className="ds-global-search" ref={ref} role="search">
      <label htmlFor="ds-global-search" className="sr-only">
        Tìm nhanh chức năng, tiêu đề đơn, người gửi hoặc mã hồ sơ
      </label>
      <span aria-hidden="true"><Icon name="search" size={16} /></span>
      <input
        id="ds-global-search"
        type="search"
        role="combobox"
        aria-autocomplete="list"
        value={text}
        autoComplete="off"
        placeholder="Tìm mã REQ, tiêu đề đơn, người gửi, chức năng…"
        aria-expanded={open && query.length >= 2}
        aria-controls="ds-global-search-results"
        onChange={(e) => {
          setText(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
      />
      {open && query.length >= 2 && (
        <ul id="ds-global-search-results" className="ds-search-results">
          {matchedFeatures.length > 0 && (
            <li className="ds-search-group-header">Chức năng điều hướng</li>
          )}
          {matchedFeatures.map((feat) => (
            <li key={`${feat.portal}:${feat.key}`}>
              <button
                type="button"
                onClick={() => {
                  setOpen(false);
                  setText("");
                  if (onNavigate) onNavigate(feat.key);
                }}
              >
                <span>
                  <strong>{feat.label}</strong> <small>{feat.hint}</small>
                </span>
                <span className="ds-search-badge">Mở ↵</span>
              </button>
            </li>
          ))}

          {items.length > 0 && (
            <li className="ds-search-group-header">Hồ sơ yêu cầu</li>
          )}
          {results.loading && !results.data && (
            <li className="muted" style={{ padding: 10 }}>
              Đang tìm kiếm hồ sơ…
            </li>
          )}
          {items.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                onClick={() => {
                  setOpen(false);
                  setText("");
                  onOpen(item.id, item);
                }}
              >
                <span className="ds-search-item-main">
                  <strong>
                    {item.code} · {item.title || item.type_name || types[item.type_code] || "Yêu cầu"}
                  </strong>
                  <small>
                    {item.type_name || types[item.type_code] || "Yêu cầu"}
                    {item.requester_name ? ` · ${item.requester_name}` : ""}
                    {item.department_name ? ` (${item.department_name})` : ""}
                  </small>
                </span>
                <Badge value={item.status} />
              </button>
            </li>
          ))}
          {!results.loading && !items.length && !matchedFeatures.length && (
            <li className="muted" style={{ padding: 10 }}>
              Không tìm thấy hồ sơ hoặc chức năng phù hợp.
            </li>
          )}
        </ul>
      )}
    </div>
  );
}

export function NotificationBell({ onOpen, onViewAll }) {
  const [open, setOpen] = useState(false);
  const feed = useResource("/api/v1/notifications?limit=6&offset=0");
  const ref = useDismiss(open, setOpen);
  const unread = Number(feed.data?.unread_count) || 0;
  async function openItem(item) {
    setOpen(false);
    if (!item.read_at) {
      await api(`/api/v1/notifications/${item.id}/read`, {
        method: "POST",
        silent: true,
      }).catch(() => {});
      feed.reload();
    }
    if (item.request_id) onOpen(item.request_id);
  }
  return (
    <div
      className="client-notifications-anchor"
      ref={ref}
      style={{ position: "relative" }}
    >
      <button
        type="button"
        className="secondary ds-icon-button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-label={unread ? `Thông báo, ${unread} chưa đọc` : "Thông báo"}
        title="Thông báo"
      >
        <svg
          viewBox="0 0 24 24"
          aria-hidden="true"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
        >
          <path d="M18 8a6 6 0 0 0-12 0c0 7-3 8-3 9h18c0-1-3-2-3-9" />
          <path d="M10 21h4" />
        </svg>
        {unread > 0 && (
          <span className="ds-count-badge">{unread > 99 ? "99+" : unread}</span>
        )}
      </button>
      {open && (
        <div className="ds-popover" role="region" aria-label="Thông báo mới">
          <div className="section-head" style={{ marginBottom: 0 }}>
            <strong>Thông báo mới</strong>
            <small className="muted">{unread} chưa đọc</small>
          </div>
          <ul>
            {(feed.data?.items || []).map((item) => (
              <li key={item.id} className={item.read_at ? "" : "is-unread"}>
                <button type="button" onClick={() => openItem(item)}>
                  <span>{formatNotificationLabel(item.label)}</span>
                  <small className="muted">{date(item.created_at)}</small>
                </button>
              </li>
            ))}
          </ul>
          {!feed.data?.items?.length && (
            <p className="muted">Chưa có thông báo nào.</p>
          )}
          <button
            type="button"
            className="secondary"
            style={{ width: "100%" }}
            onClick={() => {
              setOpen(false);
              onViewAll();
            }}
          >
            Xem tất cả thông báo
          </button>
        </div>
      )}
    </div>
  );
}
